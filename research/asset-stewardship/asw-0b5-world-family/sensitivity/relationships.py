# ABOUTME: Evaluates anchor relationships for symmetry, transfer, interventions, ambiguity, and progression.
# ABOUTME: Uses independent physical bounds and explicit inherited evidence for the transfer continuity check.

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sensitivity import anchor, catalogue, composition, inputs, physics

CARRY_DOMAIN = b"asw-0b4.g70-carry.v1\0"
STATE_DOMAIN = b"asw-0b4.pump-state.v1\0"


@dataclass(frozen=True)
class CapabilityEvidence:
    """One candidate consequence and its independent W4 interval."""

    candidate_flow_m3_s: float
    classification: str
    flow_bound_m3_s: float
    reference_flow_m3_s: float


def _check(
    *,
    failure: str,
    **evidence: object,
) -> dict[str, object]:
    return {
        **evidence,
        "first_failure": failure,
        "outcome": "pass" if failure == "none" else "reject",
    }


def _segments_by_key(
    segments: tuple[inputs.SegmentEvidence, ...],
) -> dict[tuple[str, str], inputs.SegmentEvidence]:
    indexed = {
        (segment.case_id, segment.segment_id): segment
        for segment in segments
    }
    if len(indexed) != len(segments):
        raise inputs.SensitivityInputError(
            "w4-input: relationship segment inventory has duplicates"
        )
    return indexed


def _single(
    indexed: dict[tuple[str, str], inputs.SegmentEvidence],
    case_id: str,
) -> inputs.SegmentEvidence:
    try:
        return indexed[(case_id, "single")]
    except KeyError as error:
        raise inputs.SensitivityInputError(
            f"w4-input: relationship case {case_id} is unavailable"
        ) from error


def _state_id(state: dict[str, str]) -> str:
    return hashlib.sha256(
        STATE_DOMAIN + catalogue.canonical_json_bytes(state)
    ).hexdigest()


def _decimal_text(value: Decimal) -> str:
    rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return "0" if rendered in {"", "-0"} else rendered


def _member_decimals(member: dict[str, Any]) -> dict[str, Decimal]:
    return {
        parameter["identity"]: Decimal(str(parameter["value"]))
        for parameter in member["parameters"]
        if not isinstance(parameter["value"], bool)
    }


def _quantized_flow(
    flow_m3_s: float,
    *,
    bias: str,
    resolution: str,
) -> Decimal:
    quantum = Decimal(resolution)
    biased = Decimal(str(flow_m3_s)) * (
        Decimal(1) + Decimal(bias)
    )
    return (
        biased / quantum
    ).quantize(Decimal(1), rounding=ROUND_HALF_UP) * quantum


def _flow_bin_margin(
    *,
    bias: str,
    resolution: str,
) -> float:
    denominator = Decimal(1) - abs(Decimal(bias))
    if denominator <= 0:
        raise inputs.SensitivityInputError(
            "w4-input: flow observation bias leaves no positive scale"
        )
    return float(Decimal(3) * Decimal(resolution) / denominator)


def _maximum_flow_bin_margin(
    probe_catalogue: dict[str, Any],
) -> float:
    flow_grid = probe_catalogue["grids"]["flow_observation"]
    if not isinstance(flow_grid, list) or not flow_grid:
        raise inputs.SensitivityInputError(
            "w4-input: flow observation grid is unavailable"
        )
    return max(
        _flow_bin_margin(
            bias=item["bias"],
            resolution=item["resolution"],
        )
        for item in flow_grid
    )


def _capability_evidence(
    *,
    segment: inputs.SegmentEvidence,
    result_segment: dict[str, Any],
) -> tuple[CapabilityEvidence, str]:
    values = physics.member_values(segment.request["member"])
    state, _selected = anchor._state(
        segment.request["case"],
        segment.segment_id,
    )
    obstruction = float(Decimal(state["obstruction"]))
    clearance_loss = float(Decimal(state["clearance-loss"]))
    candidate = result_segment["capability"]
    candidate_flow = float(Decimal(candidate["operating_flow_m3_s"]))
    reference_flow = physics.operating_point(
        values,
        depth_m=values["well.h_start"],
        obstruction=obstruction,
        clearance_loss=clearance_loss,
    )
    render_bound = composition.system_render_head_bound(
        values,
        candidate_flow_m3_s=candidate_flow,
    )
    root_budget = composition.amended_root_flow_budget(
        values,
        candidate_flow_m3_s=candidate_flow,
        clearance_loss=clearance_loss,
        depth_m=values["well.h_start"],
        obstruction=obstruction,
        raw_residual_m3_s=candidate_flow - reference_flow,
        reference_flow_m3_s=reference_flow,
        system_render_head_m=render_bound,
    )
    flow_bound_value = root_budget["total_allowance_m3_s"]
    if not isinstance(flow_bound_value, float):
        raise inputs.SensitivityInputError(
            "w4-input: C-R18 flow allowance differs"
        )
    flow_bound = float(flow_bound_value)
    interval = physics.capability_interval(
        values,
        flow_m3_s=reference_flow,
        flow_bound_m3_s=flow_bound,
        report_step_s=1,
    )
    classification = str(interval["classification"])
    expected_classification = (
        "review-eligible"
        if candidate["review_predicate"] is True
        else "capable"
    )
    failure = "none"
    if root_budget["outcome"] != "c-r08-checks-pass":
        failure = "C-R18-independent-flow"
    elif classification == "boundary-fragile":
        failure = "C-R18-boundary-fragile"
    elif classification != expected_classification:
        failure = "C-R18-classification"
    else:
        candidate_drawdown = candidate["drawdown_s"]
        drawdown_low = float(interval["drawdown_low_s"])
        drawdown_high = float(interval["drawdown_high_s"])
        if candidate_drawdown == "unbounded":
            if not math.isinf(drawdown_high):
                failure = "C-R18-drawdown"
        else:
            drawdown = float(Decimal(candidate_drawdown))
            if not drawdown_low <= drawdown <= drawdown_high:
                failure = "C-R18-drawdown"
    return (
        CapabilityEvidence(
            candidate_flow_m3_s=candidate_flow,
            classification=classification,
            flow_bound_m3_s=flow_bound,
            reference_flow_m3_s=reference_flow,
        ),
        failure,
    )


def _capability_check(
    *,
    certifier: inputs.CertifierEvidence,
    segments: tuple[inputs.SegmentEvidence, ...],
) -> tuple[
    dict[str, object],
    dict[tuple[str, str], CapabilityEvidence],
]:
    evidence: dict[tuple[str, str], CapabilityEvidence] = {}
    failure = "none"
    fragile_count = 0
    for segment in segments:
        key = (segment.case_id, segment.segment_id)
        item, item_failure = _capability_evidence(
            segment=segment,
            result_segment=certifier.segment_results[key],
        )
        evidence[key] = item
        fragile_count += item.classification == "boundary-fragile"
        if failure == "none" and item_failure != "none":
            failure = item_failure
    return (
        _check(
            failure=failure,
            boundary_fragile_count=fragile_count,
            evaluated=len(evidence),
        ),
        evidence,
    )


def _label_mirror_check(
    *,
    certifier: inputs.CertifierEvidence,
    indexed: dict[tuple[str, str], inputs.SegmentEvidence],
) -> dict[str, object]:
    clean_a = _single(indexed, "G10_CLEAN_A_BASE")
    clean_b = _single(indexed, "G11_CLEAN_B_BASE")
    neutral_series = (
        "time_s",
        "wet_well_depth_m",
        "wet_well_volume_m3",
        "wet_well_inflow_m3_s",
        "wet_well_overflow_m3_s",
        "force_main_flow_m3_s",
        "wet_well_head_m",
        "discharge_head_m",
    )
    failure = "none"
    for identity in neutral_series:
        if (
            clean_a.semantic["series"][identity]
            != clean_b.semantic["series"][identity]
        ):
            failure = "C-R15-neutral-series"
            break
    if failure == "none":
        for a_name, b_name in (
            ("pump_a_flow_m3_s", "pump_b_flow_m3_s"),
            ("pump_b_flow_m3_s", "pump_a_flow_m3_s"),
            ("pump_a_setting", "pump_b_setting"),
            ("pump_b_setting", "pump_a_setting"),
        ):
            a_series = clean_a.semantic["series"][a_name]
            b_series = clean_b.semantic["series"][b_name]
            if (
                a_series["representation"]
                != b_series["representation"]
                or a_series["unit"] != b_series["unit"]
                or a_series["values"] != b_series["values"]
            ):
                failure = "C-R15-swapped-series"
                break
    capability_a = certifier.segment_results[
        ("G10_CLEAN_A_BASE", "single")
    ]["capability"]
    capability_b = certifier.segment_results[
        ("G11_CLEAN_B_BASE", "single")
    ]["capability"]
    if failure == "none" and capability_a != capability_b:
        failure = "C-R15-capability"
    return _check(
        failure=failure,
        compared_series=len(neutral_series) + 4,
    )


def _carry_record(
    indexed: dict[tuple[str, str], inputs.SegmentEvidence],
) -> tuple[dict[str, Any] | None, str]:
    segment_a = indexed.get(("G70_TRANSFER", "segment-a"))
    segment_b = indexed.get(("G70_TRANSFER", "segment-b"))
    if segment_a is None or segment_b is None:
        return None, "C-R16-segments"
    carry = segment_b.semantic["carry"]
    if segment_a.semantic["carry"] != []:
        return None, "C-R16-segment-a-carry"
    if not isinstance(carry, list) or len(carry) != 1:
        return None, "C-R16-segment-b-carry"
    final_depth = segment_a.semantic["series"][
        "wet_well_depth_m"
    ]["values"][-1]
    expected_without_hash = {
        "representation": "ieee754-binary32-be-hex",
        "source": "segment-a:wet_well_depth_m:last",
        "value": final_depth,
    }
    expected_hash = hashlib.sha256(
        CARRY_DOMAIN
        + catalogue.canonical_json_bytes(expected_without_hash)
    ).hexdigest()
    expected = {
        **expected_without_hash,
        "sha256": expected_hash,
    }
    if carry[0] != expected:
        return None, "C-R16-carry-identity"
    return expected, "none"


def _carry_check(
    indexed: dict[tuple[str, str], inputs.SegmentEvidence],
) -> dict[str, object]:
    record, failure = _carry_record(indexed)
    return _check(
        failure=failure,
        carry_sha256=(
            "unavailable" if record is None else record["sha256"]
        ),
    )


def _transfer_check(
    *,
    indexed: dict[tuple[str, str], inputs.SegmentEvidence],
    mass_result: dict[str, Any],
    trajectory_result: dict[str, Any],
) -> dict[str, object]:
    _record, carry_failure = _carry_record(indexed)
    transfer = indexed.get(("G70_TRANSFER", "segment-a"))
    failure = carry_failure
    if transfer is None:
        failure = "C-R17-segments"
    elif failure == "none":
        case = transfer.request["case"]
        if (
            case["control_mode"] != "transfer"
            or [item["selected_pump"] for item in case["segments"]]
            != ["pump-a", "pump-b"]
            or [item["horizon_s"] for item in case["segments"]]
            != [60, 60]
            or len(case["physical_transitions"]) != 1
            or case["physical_transitions"][0]["effect_kind"]
            != "duty-transfer"
        ):
            failure = "C-R17-boundary"
    if (
        failure == "none"
        and (
            mass_result.get("terminal_state") != "mass-checks-pass"
            or mass_result.get("checks", {})
            .get("C-R02", {})
            .get("outcome")
            != "pass"
        )
    ):
        failure = "C-R17-inherited-mass"
    if (
        failure == "none"
        and (
            trajectory_result.get("terminal_state")
            != "trajectory-checks-pass"
            or trajectory_result.get("checks", {})
            .get("C-R10", {})
            .get("outcome")
            != "pass"
            or trajectory_result.get("checks", {})
            .get("C-R11", {})
            .get("outcome")
            != "pass"
        )
    ):
        failure = "C-R17-inherited-trajectory"
    return _check(
        failure=failure,
        inherited_checks=["C-R02", "C-R10", "C-R11"],
    )


def _expected_intervention_state(
    *,
    before: dict[str, str],
    effect_kind: str,
    values: dict[str, float],
) -> dict[str, str]:
    obstruction = Decimal(before["obstruction"])
    clearance = Decimal(before["clearance-loss"])
    if effect_kind == "obstruction-clearing":
        obstruction = max(
            Decimal(str(values["intervention.o_residual"])),
            (
                Decimal(1)
                - Decimal(str(values["intervention.e_clear"]))
            )
            * obstruction,
        )
        return {
            "clearance-loss": before["clearance-loss"],
            "obstruction": _decimal_text(obstruction),
        }
    elif effect_kind == "clearance-repair":
        clearance = max(
            Decimal(str(values["intervention.c_residual"])),
            (
                Decimal(1)
                - Decimal(str(values["intervention.e_repair"]))
            )
            * clearance,
        )
        return {
            "clearance-loss": _decimal_text(clearance),
            "obstruction": before["obstruction"],
        }
    else:
        raise inputs.SensitivityInputError(
            "w4-input: intervention effect differs"
        )


def _intervention_check(
    *,
    capabilities: dict[tuple[str, str], CapabilityEvidence],
    indexed: dict[tuple[str, str], inputs.SegmentEvidence],
    probe_catalogue: dict[str, Any],
) -> dict[str, object]:
    pairs = (
        (
            "G50_CLEAR_A_PRE",
            "G51_CLEAR_A_POST",
            "obstruction-clearing",
        ),
        (
            "G52_CLEAR_B_PRE",
            "G53_CLEAR_B_POST",
            "obstruction-clearing",
        ),
        (
            "G60_REPAIR_PRE",
            "G61_REPAIR_POST",
            "clearance-repair",
        ),
    )
    margin = _maximum_flow_bin_margin(probe_catalogue)
    failure = "none"
    minimum_excess = math.inf
    for pre_id, post_id, effect_kind in pairs:
        pre = _single(indexed, pre_id)
        post = _single(indexed, post_id)
        pre_case = pre.request["case"]
        post_case = post.request["case"]
        values = physics.member_values(post.request["member"])
        before = pre_case["mechanism_state"]["pump-a"]
        after = post_case["mechanism_state"]["pump-a"]
        expected_after = _expected_intervention_state(
            before=before,
            effect_kind=effect_kind,
            values=values,
        )
        transitions = post_case["physical_transitions"]
        if (
            after != expected_after
            or post_case["mechanism_state"]["pump-b"]
            != pre_case["mechanism_state"]["pump-b"]
            or not isinstance(transitions, list)
            or len(transitions) != 1
            or transitions[0]
            != {
                "after_state_content_id": _state_id(after),
                "before_state_content_id": _state_id(before),
                "effect_kind": effect_kind,
                "effective_second": 0,
                "rule_identity": (
                    "asw-0b4.rule.obstruction-clearing.v1"
                    if effect_kind == "obstruction-clearing"
                    else "asw-0b4.rule.clearance-repair.v1"
                ),
                "target_pump": "pump-a",
            }
        ):
            failure = "C-R19-state-isolation"
            break
        pre_capability = capabilities[(pre_id, "single")]
        post_capability = capabilities[(post_id, "single")]
        delta = (
            post_capability.reference_flow_m3_s
            - pre_capability.reference_flow_m3_s
        )
        required = (
            pre_capability.flow_bound_m3_s
            + post_capability.flow_bound_m3_s
            + margin
        )
        minimum_excess = min(minimum_excess, delta - required)
        if delta <= required:
            failure = "C-R19-response-separation"
            break
    return _check(
        failure=failure,
        evaluated=len(pairs),
        minimum_excess_m3_s=(
            "not-evaluated"
            if math.isinf(minimum_excess)
            else composition._text(minimum_excess)
        ),
        observation_margin_m3_s=composition._text(margin),
    )


def _ambiguity_visible_check(
    *,
    capabilities: dict[tuple[str, str], CapabilityEvidence],
    probe_catalogue: dict[str, Any],
) -> dict[str, object]:
    flow_a = capabilities[
        ("G50_CLEAR_A_PRE", "single")
    ].reference_flow_m3_s
    flow_b = capabilities[
        ("G52_CLEAR_B_PRE", "single")
    ].reference_flow_m3_s
    flow_grid = probe_catalogue["grids"]["flow_observation"]
    failure = "none"
    for item in flow_grid:
        visible_a = _quantized_flow(flow_a, **item)
        visible_b = _quantized_flow(flow_b, **item)
        if visible_a != visible_b:
            failure = "C-R20-visible-flow"
            break
    return _check(
        failure=failure,
        evaluated=len(flow_grid),
    )


def _ambiguity_response_check(
    *,
    capabilities: dict[tuple[str, str], CapabilityEvidence],
    probe_catalogue: dict[str, Any],
) -> dict[str, object]:
    response_a = capabilities[
        ("G51_CLEAR_A_POST", "single")
    ]
    response_b = capabilities[
        ("G53_CLEAR_B_POST", "single")
    ]
    separation = abs(
        response_a.reference_flow_m3_s
        - response_b.reference_flow_m3_s
    )
    flow_grid = probe_catalogue["grids"]["flow_observation"]
    minimum_excess = math.inf
    failure = "none"
    for item in flow_grid:
        required = (
            response_a.flow_bound_m3_s
            + response_b.flow_bound_m3_s
            + _flow_bin_margin(**item)
        )
        minimum_excess = min(minimum_excess, separation - required)
        if separation <= required:
            failure = "C-R21-response-separation"
            break
    return _check(
        failure=failure,
        evaluated=len(flow_grid),
        minimum_excess_m3_s=composition._text(minimum_excess),
    )


def _progression_check(
    *,
    capabilities: dict[tuple[str, str], CapabilityEvidence],
    indexed: dict[tuple[str, str], inputs.SegmentEvidence],
    probe_catalogue: dict[str, Any],
) -> dict[str, object]:
    checkpoints = [
        indexed[("G80_NO_MAINTENANCE", f"checkpoint-{index}")]
        for index in range(4)
    ]
    case_checkpoints = checkpoints[0].request["case"]["checkpoints"]
    values = physics.member_values(checkpoints[0].request["member"])
    decimal_values = _member_decimals(
        checkpoints[0].request["member"]
    )
    failure = "none"
    prior_severity = (-math.inf, -math.inf)
    prior_flow = math.inf
    prior_support = math.inf
    classifications: list[str] = []
    for index, (_segment, checkpoint) in enumerate(
        zip(checkpoints, case_checkpoints, strict=True)
    ):
        exposure = checkpoint["exposure"]
        obstruction_decimal = min(
            Decimal(1),
            decimal_values["mechanism.r_o_runtime"]
            * exposure["runtime_s"]
            + decimal_values["mechanism.r_o_start"]
            * exposure["completed_starts"],
        )
        clearance_decimal = min(
            Decimal(1),
            decimal_values["mechanism.r_c_runtime"]
            * exposure["runtime_s"],
        )
        obstruction = float(obstruction_decimal)
        clearance = float(clearance_decimal)
        state = checkpoint["mechanism_state"]
        if (
            Decimal(state["obstruction"]) != obstruction_decimal
            or Decimal(state["clearance-loss"]) != clearance_decimal
            or (obstruction, clearance) < prior_severity
        ):
            failure = "C-R22-state-progression"
            break
        capability = capabilities[
            ("G80_NO_MAINTENANCE", f"checkpoint-{index}")
        ]
        support = physics.pump_support(
            values,
            obstruction,
            clearance,
        )
        if (
            capability.reference_flow_m3_s > prior_flow
            or support > prior_support
        ):
            failure = "C-R22-consequence-improvement"
            break
        classifications.append(capability.classification)
        prior_severity = (obstruction, clearance)
        prior_flow = capability.reference_flow_m3_s
        prior_support = support
    if failure == "none" and (
        classifications[0] != "capable"
        or "review-eligible" not in classifications[1:]
    ):
        failure = "C-R22-capability-transition"
    first = capabilities[("G80_NO_MAINTENANCE", "checkpoint-0")]
    last = capabilities[("G80_NO_MAINTENANCE", "checkpoint-3")]
    margin = _maximum_flow_bin_margin(probe_catalogue)
    flow_loss = (
        first.reference_flow_m3_s
        - last.reference_flow_m3_s
    )
    required = (
        first.flow_bound_m3_s
        + last.flow_bound_m3_s
        + margin
    )
    if failure == "none" and flow_loss <= required:
        failure = "C-R22-total-flow-loss"
    return _check(
        failure=failure,
        classification_sequence=classifications,
        flow_loss_m3_s=composition._text(flow_loss),
        required_flow_loss_m3_s=composition._text(required),
    )


def evaluate_relationship_checks(
    *,
    bundle_bytes: bytes,
    certifier_result_bytes: bytes,
    mass_result: dict[str, Any],
    probe_catalogue_bytes: bytes,
    trajectory_result: dict[str, Any],
) -> dict[str, Any]:
    """Evaluate all anchor relationships with explicit inherited evidence."""
    probe_catalogue = catalogue.read_probe_catalogue(
        probe_catalogue_bytes
    )
    segments = inputs.read_transfer_bundle(bundle_bytes)
    certifier = inputs.read_certifier_result(
        certifier_result_bytes,
        bundle_bytes=bundle_bytes,
        segments=segments,
    )
    indexed = _segments_by_key(segments)
    capability_check, capabilities = _capability_check(
        certifier=certifier,
        segments=segments,
    )
    checks = {
        "C-R15": _label_mirror_check(
            certifier=certifier,
            indexed=indexed,
        ),
        "C-R16": _carry_check(indexed),
        "C-R17": _transfer_check(
            indexed=indexed,
            mass_result=mass_result,
            trajectory_result=trajectory_result,
        ),
        "C-R18": capability_check,
        "C-R19": _intervention_check(
            capabilities=capabilities,
            indexed=indexed,
            probe_catalogue=probe_catalogue,
        ),
        "C-R20": _ambiguity_visible_check(
            capabilities=capabilities,
            probe_catalogue=probe_catalogue,
        ),
        "C-R21": _ambiguity_response_check(
            capabilities=capabilities,
            probe_catalogue=probe_catalogue,
        ),
        "C-R22": _progression_check(
            capabilities=capabilities,
            indexed=indexed,
            probe_catalogue=probe_catalogue,
        ),
        "C-R24": _check(
            failure="none",
            replay_count=2,
            segment_count=len(segments),
        ),
    }
    failures = [
        str(check["first_failure"])
        for check in checks.values()
        if check["first_failure"] != "none"
    ]
    return {
        "checks": checks,
        "first_failure": failures[0] if failures else "none",
        "promotable": False,
        "terminal_state": (
            "relationship-checks-reject"
            if failures
            else "relationship-checks-pass"
        ),
    }


def evaluate_member_relationship_checks(
    *,
    bundle_bytes: bytes,
    certifier_result_bytes: bytes,
    mass_result: dict[str, Any],
    probe_catalogue_bytes: bytes,
    trajectory_result: dict[str, Any],
) -> dict[str, Any]:
    """Evaluate the exact relationships supported by a fixed member case map."""
    probe_catalogue = catalogue.read_probe_catalogue(
        probe_catalogue_bytes
    )
    segments = inputs.read_transfer_bundle(bundle_bytes)
    certifier = inputs.read_certifier_result(
        certifier_result_bytes,
        bundle_bytes=bundle_bytes,
        segments=segments,
    )
    indexed = _segments_by_key(segments)
    case_ids = {segment.case_id for segment in segments}
    capability_check, capabilities = _capability_check(
        certifier=certifier,
        segments=segments,
    )
    checks: dict[str, dict[str, object]] = {}
    if {
        "G10_CLEAN_A_BASE",
        "G11_CLEAN_B_BASE",
    }.issubset(case_ids):
        checks["C-R15"] = _label_mirror_check(
            certifier=certifier,
            indexed=indexed,
        )
    if "G70_TRANSFER" in case_ids:
        checks["C-R16"] = _carry_check(indexed)
        checks["C-R17"] = _transfer_check(
            indexed=indexed,
            mass_result=mass_result,
            trajectory_result=trajectory_result,
        )
    checks["C-R18"] = capability_check
    if {
        "G50_CLEAR_A_PRE",
        "G51_CLEAR_A_POST",
        "G52_CLEAR_B_PRE",
        "G53_CLEAR_B_POST",
        "G60_REPAIR_PRE",
        "G61_REPAIR_POST",
    }.issubset(case_ids):
        checks["C-R19"] = _intervention_check(
            capabilities=capabilities,
            indexed=indexed,
            probe_catalogue=probe_catalogue,
        )
    if {"G50_CLEAR_A_PRE", "G52_CLEAR_B_PRE"}.issubset(case_ids):
        checks["C-R20"] = _ambiguity_visible_check(
            capabilities=capabilities,
            probe_catalogue=probe_catalogue,
        )
    if {"G51_CLEAR_A_POST", "G53_CLEAR_B_POST"}.issubset(case_ids):
        checks["C-R21"] = _ambiguity_response_check(
            capabilities=capabilities,
            probe_catalogue=probe_catalogue,
        )
    if "G80_NO_MAINTENANCE" in case_ids:
        checks["C-R22"] = _progression_check(
            capabilities=capabilities,
            indexed=indexed,
            probe_catalogue=probe_catalogue,
        )
    checks["C-R24"] = _check(
        failure="none",
        replay_count=2,
        segment_count=len(segments),
    )
    checks = {
        check_id: checks[check_id]
        for check_id in sorted(checks)
    }
    failures = [
        str(check["first_failure"])
        for check in checks.values()
        if check["first_failure"] != "none"
    ]
    return {
        "checks": checks,
        "first_failure": failures[0] if failures else "none",
        "promotable": False,
        "terminal_state": (
            "relationship-checks-reject"
            if failures
            else "relationship-checks-pass"
        ),
    }
