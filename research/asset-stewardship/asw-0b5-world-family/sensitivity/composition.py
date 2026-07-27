# ABOUTME: Composes W3 residual evidence with preregistered W4 numerical budgets.
# ABOUTME: Rejects unavoidable hard-ceiling conflicts before candidate residual comparison.

from __future__ import annotations

import hashlib
import math
import struct
from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from sensitivity import catalogue, inputs, physics, tolerances

COMPOSITION_RESULT_DOMAIN = b"asw-0b5.w4-composition-result.v1\0"


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
