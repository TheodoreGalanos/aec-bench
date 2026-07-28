# ABOUTME: Composes W3 residual evidence with preregistered W4 numerical budgets.
# ABOUTME: Rejects unavoidable hard-ceiling conflicts before candidate residual comparison.

from __future__ import annotations

import hashlib
import math
import struct
from collections.abc import Mapping
from decimal import Decimal
from itertools import product
from typing import Any

from sensitivity import catalogue, inputs, physics, tolerances

COMPOSITION_RESULT_DOMAIN = b"asw-0b5.w4-composition-result.v1\0"
RENDER_QUANTUM_HALF = 0.5e-9


def _text(value: float) -> str:
    if not math.isfinite(value):
        raise physics.SensitivityPhysicsError("composition value is non-finite")
    rendered = format(value, ".17f").rstrip("0").rstrip(".")
    return "0" if rendered in {"", "-0"} else rendered


def _binary32(value: str) -> float:
    if len(value) != 8 or value.lower() != value:
        raise inputs.SensitivityInputError("w4-input: binary32 value differs")
    decoded = float(struct.unpack(">f", bytes.fromhex(value))[0])
    if not math.isfinite(decoded) or value == "80000000":
        raise inputs.SensitivityInputError("w4-input: binary32 value differs")
    return decoded


def _stringify_budget(value: Mapping[str, object]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, child in value.items():
        if isinstance(child, float):
            result[key] = _text(child)
        elif isinstance(child, Mapping):
            result[key] = _stringify_budget(child)
        else:
            result[key] = child
    return result


def _result_id(value: dict[str, Any]) -> str:
    payload = {key: child for key, child in value.items() if key != "result_content_id"}
    return hashlib.sha256(COMPOSITION_RESULT_DOMAIN + catalogue.canonical_json_bytes(payload)).hexdigest()


def root_flow_budget_lower_bound(
    values: dict[str, float],
    *,
    candidate_flow_m3_s: float,
    clearance_loss: float,
    depth_m: float,
    obstruction: float,
    reference_flow_m3_s: float,
    curve_segments: int = 32,
) -> dict[str, object]:
    """Prove the minimum C-R08 allowance before optional positive terms."""
    slope = physics.root_slope(
        values,
        flow_m3_s=reference_flow_m3_s,
        depth_m=depth_m,
        obstruction=obstruction,
        clearance_loss=clearance_loss,
    )
    curve_head = tolerances.curve_head_bound(
        head_zero_m=Decimal(str(values["pump.H_0"])),
        obstruction=Decimal(str(obstruction)),
        clearance_loss=Decimal(str(clearance_loss)),
        obstruction_coefficient=Decimal(str(values["mechanism.a_o"])),
        clearance_coefficient=Decimal(str(values["mechanism.a_c"])),
        segments=curve_segments,
    )
    support = physics.pump_support(values, obstruction, clearance_loss)
    root_bound = max(
        support / 2.0**129,
        math.ulp(reference_flow_m3_s),
    )
    terms = {
        "binary32_candidate_m3_s": tolerances.binary32_bound(candidate_flow_m3_s),
        "binary64_reference_m3_s": tolerances.binary64_guard(reference_flow_m3_s),
        "bisection_m3_s": root_bound,
        "curve_m3_s": tolerances.outward_divide(curve_head, slope),
        "dynamic_flow_m3_s": 0.001 * reference_flow_m3_s,
    }
    lower_bound = tolerances.outward_sum(list(terms.values()))
    relative_ceiling = 0.001 * abs(reference_flow_m3_s)
    observation_ceiling = 0.25 * values["observation.flow_resolution"]
    hard_ceiling = min(relative_ceiling, observation_ceiling)
    exceeds = lower_bound > hard_ceiling
    return {
        "derived_lower_bound_m3_s": lower_bound,
        "first_failure": ("C-R08-derived-budget-lower-bound-exceeds-relative-ceiling" if exceeds else "none"),
        "hard_ceiling_m3_s": hard_ceiling,
        "observation_hard_ceiling_m3_s": observation_ceiling,
        "outcome": "w4-budget-reject" if exceeds else "budget-lower-bound-pass",
        "relative_hard_ceiling_m3_s": relative_ceiling,
        "terms": terms,
    }


def amended_net_head_budget(
    values: dict[str, float],
    *,
    clearance_loss: float,
    discharge_head_m: float,
    obstruction: float,
    raw_residual_m: float,
    system_render_head_m: float,
    wet_well_head_m: float,
    curve_segments: int = 32,
) -> dict[str, object]:
    """Compose the curve-aware C-R07 allowance and unchanged head ceiling."""
    curve_head = tolerances.curve_head_bound(
        head_zero_m=Decimal(str(values["pump.H_0"])),
        obstruction=Decimal(str(obstruction)),
        clearance_loss=Decimal(str(clearance_loss)),
        obstruction_coefficient=Decimal(str(values["mechanism.a_o"])),
        clearance_coefficient=Decimal(str(values["mechanism.a_c"])),
        segments=curve_segments,
    )
    reference_head = discharge_head_m - wet_well_head_m
    terms = {
        "binary32_discharge_head_m": tolerances.binary32_bound(
            discharge_head_m
        ),
        "binary32_wet_well_head_m": tolerances.binary32_bound(
            wet_well_head_m
        ),
        "binary64_system_head_m": tolerances.binary64_guard(reference_head),
        "curve_head_m": curve_head,
        "curve_render_head_m": 0.5e-9,
        "system_render_head_m": system_render_head_m,
    }
    derived_allowance = tolerances.outward_sum(list(terms.values()))
    hard_ceiling = 0.001 * abs(reference_head)
    if derived_allowance > hard_ceiling:
        first_failure = "C-R07-derived-allowance-exceeds-head-ceiling"
        outcome = "w4-budget-reject"
    elif abs(raw_residual_m) > derived_allowance:
        first_failure = "C-R07-residual-exceeds-derived-allowance"
        outcome = "w4-numerical-reject"
    else:
        first_failure = "none"
        outcome = "c-r07-checks-pass"
    return {
        "derived_allowance_m": derived_allowance,
        "first_failure": first_failure,
        "hard_ceiling_m": hard_ceiling,
        "outcome": outcome,
        "raw_residual_m": raw_residual_m,
        "reference_head_m": reference_head,
        "terms": terms,
    }


def amended_root_flow_budget(
    values: dict[str, float],
    *,
    candidate_flow_m3_s: float,
    clearance_loss: float,
    depth_m: float,
    obstruction: float,
    raw_residual_m3_s: float,
    reference_flow_m3_s: float,
    system_render_head_m: float,
    curve_segments: int = 32,
) -> dict[str, object]:
    """Compose the amended C-R08 dynamic and numerical ceilings separately."""
    slope = physics.root_slope(
        values,
        flow_m3_s=reference_flow_m3_s,
        depth_m=depth_m,
        obstruction=obstruction,
        clearance_loss=clearance_loss,
    )
    curve_head = tolerances.curve_head_bound(
        head_zero_m=Decimal(str(values["pump.H_0"])),
        obstruction=Decimal(str(obstruction)),
        clearance_loss=Decimal(str(clearance_loss)),
        obstruction_coefficient=Decimal(str(values["mechanism.a_o"])),
        clearance_coefficient=Decimal(str(values["mechanism.a_c"])),
        segments=curve_segments,
    )
    support = physics.pump_support(values, obstruction, clearance_loss)
    root_bound = max(
        support / 2.0**129,
        math.ulp(reference_flow_m3_s),
    )
    numerical_terms = {
        "binary32_candidate_m3_s": tolerances.binary32_bound(candidate_flow_m3_s),
        "binary64_reference_m3_s": tolerances.binary64_guard(reference_flow_m3_s),
        "bisection_m3_s": root_bound,
        "curve_m3_s": tolerances.outward_divide(curve_head, slope),
        "system_render_m3_s": tolerances.outward_divide(
            system_render_head_m,
            slope,
        ),
    }
    numerical_allowance = tolerances.outward_sum(list(numerical_terms.values()))
    dynamic_allowance = 0.001 * abs(reference_flow_m3_s)
    total_allowance = tolerances.outward_sum(
        [dynamic_allowance, numerical_allowance]
    )
    relative_ceiling = 0.001 * abs(reference_flow_m3_s)
    observation_ceiling = 0.25 * values["observation.flow_resolution"]
    hard_ceiling = min(relative_ceiling, observation_ceiling)
    if dynamic_allowance > hard_ceiling:
        first_failure = "C-R08-dynamic-allowance-exceeds-hard-ceiling"
        outcome = "w4-budget-reject"
    elif numerical_allowance > hard_ceiling:
        first_failure = "C-R08-numerical-allowance-exceeds-hard-ceiling"
        outcome = "w4-budget-reject"
    elif abs(raw_residual_m3_s) > total_allowance:
        first_failure = "C-R08-residual-exceeds-amended-allowance"
        outcome = "w4-numerical-reject"
    else:
        first_failure = "none"
        outcome = "c-r08-checks-pass"
    return {
        "dynamic_allowance_m3_s": dynamic_allowance,
        "first_failure": first_failure,
        "hard_ceiling_m3_s": hard_ceiling,
        "numerical_allowance_m3_s": numerical_allowance,
        "observation_hard_ceiling_m3_s": observation_ceiling,
        "outcome": outcome,
        "raw_residual_m3_s": raw_residual_m3_s,
        "relative_hard_ceiling_m3_s": relative_ceiling,
        "terms": {
            **numerical_terms,
            "dynamic_flow_m3_s": dynamic_allowance,
        },
        "total_allowance_m3_s": total_allowance,
    }


def system_render_head_bound(
    values: dict[str, float],
    *,
    candidate_flow_m3_s: float,
) -> float:
    """Enclose system-loss changes from declared rendering and flow representation."""
    identities = (
        "fluid.rho",
        "fluid.mu",
        "fluid.g",
        "system.L",
        "system.D",
        "system.epsilon",
        "system.K_minor",
    )
    canonical = physics.system_loss_head(values, candidate_flow_m3_s)
    flow_bound = tolerances.outward_sum(
        [
            RENDER_QUANTUM_HALF,
            tolerances.binary32_bound(candidate_flow_m3_s),
        ]
    )
    maximum = 0.0
    for signs in product((-1.0, 1.0), repeat=len(identities) + 1):
        corner = dict(values)
        for identity, sign in zip(identities, signs[:-1], strict=True):
            corner[identity] += sign * RENDER_QUANTUM_HALF
        flow = candidate_flow_m3_s + signs[-1] * flow_bound
        if flow <= 0.0:
            raise physics.SensitivityPhysicsError(
                "system-render flow interval is not positive"
            )
        difference = abs(physics.system_loss_head(corner, flow) - canonical)
        maximum = max(maximum, difference)
    return math.nextafter(maximum, math.inf)


def compose_amended_hydraulic_checkpoint(
    *,
    bundle_bytes: bytes,
    certifier_result_bytes: bytes,
) -> dict[str, Any]:
    """Evaluate the two approved successor-only hydraulic amendments."""
    segments = inputs.read_transfer_bundle(bundle_bytes)
    certifier = inputs.read_certifier_result(
        certifier_result_bytes,
        bundle_bytes=bundle_bytes,
        segments=segments,
    )
    matching = [
        segment
        for segment in segments
        if segment.case_id == "G12_CLEAN_ASSESS"
        and segment.segment_id == "single"
    ]
    if len(matching) != 1:
        raise inputs.SensitivityInputError(
            "w4-input: exact G12 segment is unavailable"
        )
    segment = matching[0]
    request = segment.request
    case = request["case"]
    if (
        case["control_mode"] != "forced-on"
        or case["selected_pump"] != "pump-a"
    ):
        raise inputs.SensitivityInputError(
            "w4-input: G12 clean forced reference differs"
        )
    values = physics.member_values(request["member"])
    obstruction = float(
        Decimal(case["mechanism_state"]["pump-a"]["obstruction"])
    )
    clearance_loss = float(
        Decimal(case["mechanism_state"]["pump-a"]["clearance-loss"])
    )
    initial_depth = values["well.h_start"]
    initial_flow = physics.operating_point(
        values,
        depth_m=initial_depth,
        obstruction=obstruction,
        clearance_loss=clearance_loss,
    )
    settling = physics.dynamic_settling(
        values,
        flow_m3_s=initial_flow,
        depth_m=initial_depth,
        obstruction=obstruction,
        clearance_loss=clearance_loss,
        report_step_s=1,
    )
    sample_second = int(settling["settling_time_s"]) + 1
    index = sample_second - 1
    series = segment.semantic["series"]
    candidate_flow = _binary32(
        series["pump_a_flow_m3_s"]["values"][index]
    )
    discharge_head = _binary32(
        series["discharge_head_m"]["values"][index]
    )
    wet_well_head = _binary32(
        series["wet_well_head_m"]["values"][index]
    )
    reference_flow = physics.operating_point(
        values,
        depth_m=wet_well_head,
        obstruction=obstruction,
        clearance_loss=clearance_loss,
    )
    result_segment = certifier.segment_results[
        (segment.case_id, segment.segment_id)
    ]
    c_r07_residual = float(
        Decimal(result_segment["residuals"]["C-R07"]["values"][index])
    )
    c_r08_residual = float(
        Decimal(result_segment["residuals"]["C-R08"]["values"][index])
    )
    system_render = system_render_head_bound(
        values,
        candidate_flow_m3_s=candidate_flow,
    )
    c_r07 = amended_net_head_budget(
        values,
        clearance_loss=clearance_loss,
        discharge_head_m=discharge_head,
        obstruction=obstruction,
        raw_residual_m=c_r07_residual,
        system_render_head_m=system_render,
        wet_well_head_m=wet_well_head,
    )
    c_r08 = amended_root_flow_budget(
        values,
        candidate_flow_m3_s=candidate_flow,
        clearance_loss=clearance_loss,
        depth_m=wet_well_head,
        obstruction=obstruction,
        raw_residual_m3_s=c_r08_residual,
        reference_flow_m3_s=reference_flow,
        system_render_head_m=system_render,
    )
    checks = {
        "C-R07": _stringify_budget(c_r07),
        "C-R08": _stringify_budget(c_r08),
    }
    failures = [
        value["first_failure"]
        for value in (c_r07, c_r08)
        if value["first_failure"] != "none"
    ]
    return {
        "checks": checks,
        "first_failure": failures[0] if failures else "none",
        "promotable": False,
        "sample_second": sample_second,
        "segment": {
            "case_id": segment.case_id,
            "segment_id": segment.segment_id,
        },
        "system_render_head_m": _text(system_render),
        "terminal_state": (
            "amended-hydraulic-checks-pass"
            if not failures
            else "amended-hydraulic-checks-reject"
        ),
    }


def _forced_clean_budget(
    segment: inputs.SegmentEvidence,
    result_segment: dict[str, Any],
) -> dict[str, object]:
    request = segment.request
    case = request["case"]
    if (
        case["case_id"] != "G12_CLEAN_ASSESS"
        or case["control_mode"] != "forced-on"
        or case["selected_pump"] != "pump-a"
    ):
        raise inputs.SensitivityInputError("w4-input: G12 clean forced reference differs")
    values = physics.member_values(request["member"])
    initial_depth = values["well.h_start"]
    initial_flow = physics.operating_point(
        values,
        depth_m=initial_depth,
        obstruction=0.0,
        clearance_loss=0.0,
    )
    settling = physics.dynamic_settling(
        values,
        flow_m3_s=initial_flow,
        depth_m=initial_depth,
        obstruction=0.0,
        clearance_loss=0.0,
        report_step_s=1,
    )
    sample_second = int(settling["settling_time_s"]) + 1
    if sample_second > case["horizon_s"]:
        raise physics.SensitivityPhysicsError("G12 horizon does not contain a steady-eligible sample")
    reference = physics.rk4_advance(
        values,
        clearance_loss=0.0,
        depth_m=initial_depth,
        duration_s=float(sample_second),
        inflow_m3_s=values["inflow.Q_assess"],
        obstruction=0.0,
        running=True,
        step_s=0.5,
    )
    reference_flow = physics.operating_point(
        values,
        depth_m=reference.depth_m,
        obstruction=0.0,
        clearance_loss=0.0,
    )
    series = segment.semantic["series"]
    candidate_flow = _binary32(series["pump_a_flow_m3_s"]["values"][sample_second - 1])
    residual_values = result_segment["residuals"]["C-R08"]["values"]
    if not isinstance(residual_values, list) or len(residual_values) != case["horizon_s"]:
        raise inputs.SensitivityInputError("w4-input: G12 C-R08 residual vector differs")
    budget = root_flow_budget_lower_bound(
        values,
        candidate_flow_m3_s=candidate_flow,
        clearance_loss=0.0,
        depth_m=reference.depth_m,
        obstruction=0.0,
        reference_flow_m3_s=reference_flow,
    )
    return {
        "budget": _stringify_budget(budget),
        "candidate_flow_m3_s": _text(candidate_flow),
        "case_id": case["case_id"],
        "raw_residual_m3_s": residual_values[sample_second - 1],
        "reference_depth_m": _text(reference.depth_m),
        "reference_flow_m3_s": _text(reference_flow),
        "sample_second": sample_second,
        "segment_id": segment.segment_id,
        "settling": _stringify_budget(settling),
    }


def compose_generation(
    *,
    bundle_bytes: bytes,
    certifier_result_bytes: bytes,
) -> dict[str, Any]:
    """Compose one exact W3 handoff until the first ordered W4 hard rejection."""
    segments = inputs.read_transfer_bundle(bundle_bytes)
    certifier = inputs.read_certifier_result(
        certifier_result_bytes,
        bundle_bytes=bundle_bytes,
        segments=segments,
    )
    matching = [
        segment for segment in segments if segment.case_id == "G12_CLEAN_ASSESS" and segment.segment_id == "single"
    ]
    if len(matching) != 1:
        raise inputs.SensitivityInputError("w4-input: exact G12 segment is unavailable")
    segment = matching[0]
    evidence = _forced_clean_budget(
        segment,
        certifier.segment_results[(segment.case_id, segment.segment_id)],
    )
    budget = evidence["budget"]
    if not isinstance(budget, dict) or budget["outcome"] != "w4-budget-reject":
        raise physics.SensitivityPhysicsError("C-R08 minimum budget unexpectedly fits its hard ceiling")
    result: dict[str, Any] = {
        "authorities": {
            "composition_repair_sha256": ("38ca15bf46f67ee98aa66539701bbd8fc1889c1e268d42f0f724f7942b3c2ff8"),
            "engine_mapping_repair_sha256": ("862ef1f5fc70d882d156c0ef9842bb565301344725d2206edfa49c10910576ca"),
            "profile_id": "AU-NSW-LH-SYN-SPS-v1",
            "w4_probe_catalogue_sha256": catalogue.PROBE_CATALOGUE_SHA256,
            "w4_sha256": ("56502750816efec73ed821ac00ee5ead4ed76ba05e243992f794005980c19b7f"),
        },
        "bundle_sha256": hashlib.sha256(bundle_bytes).hexdigest(),
        "certifier_result_content_id": certifier.result_content_id,
        "evidence": evidence,
        "evaluation_scope": ("ordered-stop-after-first-unavoidable-budget-rejection"),
        "first_failure": ("C-R08-derived-budget-lower-bound-exceeds-relative-ceiling"),
        "promotable": False,
        "result_content_id": "",
        "schema_id": "asw-0b5.w4-composition-result.v1",
        "terminal_state": "w4-budget-reject",
    }
    result["result_content_id"] = _result_id(result)
    return result


def composition_result_bytes(value: dict[str, Any]) -> bytes:
    """Return exact canonical W4 composition-result bytes."""
    if value.get("result_content_id") != _result_id(value):
        raise inputs.SensitivityInputError("w4-input: composition result identity differs")
    return catalogue.canonical_json_bytes(value)
