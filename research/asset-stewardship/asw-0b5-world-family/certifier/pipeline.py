# ABOUTME: Runs W3 request, case, curve, semantic, replay, carry, and qualitative certification stages.
# ABOUTME: Returns threshold-free observations only and raises typed candidate rejections before W4 acceptance.

from __future__ import annotations

import hashlib
import math
from decimal import Decimal
from typing import Any

from certifier import boundary, candidate, cases, observations, physics

CARRY_DOMAIN = b"asw-0b4.g70-carry.v1\0"
RESIDUAL_NAMES = (
    "Storage identity",
    "Step mass balance",
    "Cumulative mass balance",
    "Candidate inflow",
    "Pump sum",
    "Candidate pump head",
    "Candidate system head",
    "Independent root flow",
    "Full-pipe applicability",
    "Reference depth trajectory",
    "Reference flow trajectory",
    "Control edge",
    "Off-state flow",
    "On-state flow",
    "Label mirror",
    "Carry continuity",
    "Transfer hydraulic continuity",
    "Capability",
    "Intervention delta",
    "Ambiguous visible flow",
    "Ambiguous response",
    "No-maintenance progression",
    "Engine continuity diagnostic",
    "Replay identity",
)


class PipelineReject(ValueError):
    """A deterministic candidate-owned W3 rejection."""

    def __init__(self, terminal_state: str, stage: str) -> None:
        self.terminal_state = terminal_state
        self.stage = stage
        super().__init__(f"{terminal_state}:{stage}")


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _exact_sha(value: object, stage: str) -> str:
    if (
        not isinstance(value, str)
        or boundary.LOWER_SHA256.fullmatch(value) is None
    ):
        raise PipelineReject("structural-reject", stage)
    return value


def _curve_for_state(
    raw: bytes,
    *,
    representation: str,
    state: dict[str, str],
    values: dict[str, Decimal],
) -> dict[str, Any]:
    parsed = candidate.read_curve(raw, representation)
    expected = physics.reconstruct_curve(
        values,
        clearance_loss=state["clearance-loss"],
        obstruction=state["obstruction"],
        representation=representation,
    )
    if parsed != expected or raw != boundary.canonical_json_bytes(expected):
        raise PipelineReject("exact-reject", "curve-reconstruction")
    return parsed


def _curve_evidence(
    segment: candidate.SegmentInputs,
    semantic: dict[str, Any],
    request: dict[str, Any],
    values: dict[str, Decimal],
) -> None:
    pump_a_state, pump_b_state, _ = observations.segment_state(
        request["case"],
        segment.segment_id,
    )
    roles = segment.roles
    if pump_a_state == pump_b_state and (
        roles["pump-a-original-curve"]
        != roles["pump-b-original-curve"]
        or roles["pump-a-engine-curve"]
        != roles["pump-b-engine-curve"]
    ):
        raise PipelineReject(
            "exact-reject",
            "label-curve-symmetry",
        )
    _curve_for_state(
        roles["pump-a-original-curve"],
        representation="asw-0b4.pump3-curve.v1",
        state=pump_a_state,
        values=values,
    )
    _curve_for_state(
        roles["pump-a-engine-curve"],
        representation="asw-0b5.net-head-pump3-curve.v1",
        state=pump_a_state,
        values=values,
    )
    _curve_for_state(
        roles["pump-b-original-curve"],
        representation="asw-0b4.pump3-curve.v1",
        state=pump_b_state,
        values=values,
    )
    _curve_for_state(
        roles["pump-b-engine-curve"],
        representation="asw-0b5.net-head-pump3-curve.v1",
        state=pump_b_state,
        values=values,
    )
    expected = {
        "pump_a_engine_curve_sha256": _sha256(roles["pump-a-engine-curve"]),
        "pump_a_original_curve_sha256": _sha256(
            roles["pump-a-original-curve"]
        ),
        "pump_b_engine_curve_sha256": _sha256(roles["pump-b-engine-curve"]),
        "pump_b_original_curve_sha256": _sha256(
            roles["pump-b-original-curve"]
        ),
    }
    if semantic["curve_evidence"] != expected:
        raise PipelineReject("structural-reject", "curve-evidence-binding")


def _verify_replay(
    segments: tuple[candidate.SegmentInputs, ...],
    case_ids: tuple[str, ...],
) -> None:
    per_replay = sum(
        candidate.SEGMENT_COUNT_BY_CASE[case_id]
        for case_id in case_ids
    )
    if len(segments) != 2 * per_replay:
        raise PipelineReject("certifier-input-reject", "replay-cardinality")
    for first, second in zip(
        segments[:per_replay],
        segments[per_replay:],
        strict=True,
    ):
        if (
            first.replay_ordinal != 0
            or second.replay_ordinal != 1
            or first.case_id != second.case_id
            or first.segment_id != second.segment_id
            or first.roles != second.roles
        ):
                raise PipelineReject("exact-reject", "replay-identity")


def _require_ambiguity_request_distinction(
    segments: tuple[candidate.SegmentInputs, ...],
    case_ids: tuple[str, ...],
) -> None:
    if not {
        "G51_CLEAR_A_POST",
        "G53_CLEAR_B_POST",
    }.issubset(case_ids):
        return
    first_replay = [
        segment
        for segment in segments
        if segment.replay_ordinal == 0
        and segment.case_id
        in {"G51_CLEAR_A_POST", "G53_CLEAR_B_POST"}
    ]
    requests = {
        segment.case_id: candidate.read_request(
            segment.roles["request"]
        )
        for segment in first_replay
    }
    if set(requests) != {
        "G51_CLEAR_A_POST",
        "G53_CLEAR_B_POST",
    }:
        raise PipelineReject(
            "certifier-input-reject",
            "ambiguity-request-inventory",
        )
    state_a = requests["G51_CLEAR_A_POST"]["case"][
        "mechanism_state"
    ]["pump-a"]
    state_b = requests["G53_CLEAR_B_POST"]["case"][
        "mechanism_state"
    ]["pump-a"]
    if state_a == state_b:
        raise PipelineReject(
            "qualitative-reject",
            "ambiguity-response-collapse",
        )


def _carry_value(
    prior: dict[str, Any] | None,
    semantic: dict[str, Any],
    *,
    case_id: str,
    segment_id: str,
) -> float | None:
    carry = semantic["carry"]
    if case_id != "G70_TRANSFER":
        if carry != []:
            raise PipelineReject("exact-reject", "unexpected-carry")
        return None
    if segment_id == "segment-a":
        if prior is not None or carry != []:
            raise PipelineReject("exact-reject", "transfer-segment-a-carry")
        return None
    if prior is None or not isinstance(carry, list) or len(carry) != 1:
        raise PipelineReject("exact-reject", "transfer-segment-b-carry")
    record = carry[0]
    if not isinstance(record, dict) or set(record) != {
        "representation",
        "sha256",
        "source",
        "value",
    }:
        raise PipelineReject("exact-reject", "transfer-carry-shape")
    value = prior["series"]["wet_well_depth_m"]["values"][-1]
    expected_without_hash = {
        "representation": "ieee754-binary32-be-hex",
        "source": "segment-a:wet_well_depth_m:last",
        "value": value,
    }
    expected_hash = hashlib.sha256(
        CARRY_DOMAIN + boundary.canonical_json_bytes(expected_without_hash)
    ).hexdigest()
    if record != {**expected_without_hash, "sha256": expected_hash}:
        raise PipelineReject("exact-reject", "transfer-carry-identity")
    return candidate.decode_binary32(value)


def _decimal_text(value: float) -> str:
    if not math.isfinite(value):
        return "unbounded"
    rendered = format(value, ".17f").rstrip("0").rstrip(".")
    return "0" if rendered in {"", "-0"} else rendered


def _capability(
    request: dict[str, Any],
    values: dict[str, Decimal],
    segment_id: str,
) -> dict[str, Any]:
    pump_a, pump_b, selected = observations.segment_state(
        request["case"],
        segment_id,
    )
    state = pump_a if selected != "pump-b" else pump_b
    result = physics.capability(
        values,
        float(state["obstruction"]),
        float(state["clearance-loss"]),
    )
    return {
        "drawdown_s": _decimal_text(float(result["drawdown_s"])),
        "operating_flow_m3_s": _decimal_text(
            float(result["operating_flow_m3_s"])
        ),
        "review_predicate": result["review_predicate"],
    }


def _quantized_visible_flow(
    capability: dict[str, Any],
    values: dict[str, Decimal],
) -> Decimal:
    flow = Decimal(capability["operating_flow_m3_s"])
    biased = flow * (Decimal(1) + values["observation.flow_bias"])
    return physics.quantize_half_up(
        biased,
        values["observation.flow_resolution"],
    )


def _require_relations(
    internal: dict[str, list[dict[str, Any]]],
    values: dict[str, Decimal],
    *,
    require_anchor_witnesses: bool,
) -> None:
    if {
        "G10_CLEAN_A_BASE",
        "G11_CLEAN_B_BASE",
    }.issubset(internal):
        clean_a = internal["G10_CLEAN_A_BASE"][0]["semantic"]
        clean_b = internal["G11_CLEAN_B_BASE"][0]["semantic"]
        neutral = (
            "time_s",
            "wet_well_depth_m",
            "wet_well_volume_m3",
            "wet_well_inflow_m3_s",
            "wet_well_overflow_m3_s",
            "force_main_flow_m3_s",
            "wet_well_head_m",
            "discharge_head_m",
        )
        if any(
            clean_a["series"][identity]["values"]
            != clean_b["series"][identity]["values"]
            for identity in neutral
        ):
            raise PipelineReject(
                "qualitative-reject",
                "label-mirror-hydraulics",
            )
        for a_name, b_name in (
            ("pump_a_flow_m3_s", "pump_b_flow_m3_s"),
            ("pump_b_flow_m3_s", "pump_a_flow_m3_s"),
            ("pump_a_setting", "pump_b_setting"),
            ("pump_b_setting", "pump_a_setting"),
        ):
            if (
                clean_a["series"][a_name]["values"]
                != clean_b["series"][b_name]["values"]
            ):
                raise PipelineReject(
                    "exact-reject",
                    "label-mirror-series",
                )
    capabilities = {
        case_id: float(items[0]["capability"]["operating_flow_m3_s"])
        for case_id, items in internal.items()
    }
    ordered_relations = (
        ("G12_CLEAN_ASSESS", "G20_OBSTRUCTION_HALF"),
        ("G20_OBSTRUCTION_HALF", "G21_OBSTRUCTION_TRIGGER"),
        ("G21_OBSTRUCTION_TRIGGER", "G22_OBSTRUCTION_UPPER"),
        ("G12_CLEAN_ASSESS", "G30_CLEARANCE_HALF"),
        ("G30_CLEARANCE_HALF", "G31_CLEARANCE_UPPER"),
        ("G20_OBSTRUCTION_HALF", "G40_COMBINED_HALF"),
        ("G30_CLEARANCE_HALF", "G40_COMBINED_HALF"),
        ("G40_COMBINED_HALF", "G41_COMBINED_UPPER"),
        ("G51_CLEAR_A_POST", "G50_CLEAR_A_PRE"),
        ("G53_CLEAR_B_POST", "G52_CLEAR_B_PRE"),
        ("G61_REPAIR_POST", "G60_REPAIR_PRE"),
    )
    for better, worse in ordered_relations:
        if better not in capabilities or worse not in capabilities:
            continue
        if capabilities[better] < capabilities[worse]:
            raise PipelineReject(
                "qualitative-reject",
                f"capability-order-{better}-{worse}",
            )
    if require_anchor_witnesses and "G12_CLEAN_ASSESS" in internal and (
        internal["G12_CLEAN_ASSESS"][0]["capability"]["review_predicate"]
        is not False
    ):
        raise PipelineReject("qualitative-reject", "clean-capability")
    if require_anchor_witnesses and "G21_OBSTRUCTION_TRIGGER" in internal and (
        internal["G21_OBSTRUCTION_TRIGGER"][0]["capability"][
            "review_predicate"
        ]
        is not True
    ):
        raise PipelineReject("qualitative-reject", "trigger-capability")
    if require_anchor_witnesses and "G41_COMBINED_UPPER" in internal and (
        internal["G41_COMBINED_UPPER"][0]["capability"]["review_predicate"]
        is not True
    ):
        raise PipelineReject("qualitative-reject", "upper-capability")
    if {"G50_CLEAR_A_PRE", "G52_CLEAR_B_PRE"}.issubset(internal):
        history_a = internal["G50_CLEAR_A_PRE"][0]["capability"]
        history_b = internal["G52_CLEAR_B_PRE"][0]["capability"]
        if _quantized_visible_flow(
            history_a,
            values,
        ) != _quantized_visible_flow(
            history_b,
            values,
        ):
            raise PipelineReject(
                "exact-reject",
                "ambiguity-visible-flow",
            )
    if {"G51_CLEAR_A_POST", "G53_CLEAR_B_POST"}.issubset(internal):
        response_a = float(
            internal["G51_CLEAR_A_POST"][0]["capability"][
                "operating_flow_m3_s"
            ]
        )
        response_b = float(
            internal["G53_CLEAR_B_POST"][0]["capability"][
                "operating_flow_m3_s"
            ]
        )
        if response_a == response_b:
            raise PipelineReject(
                "qualitative-reject",
                "ambiguity-response",
            )
    if "G80_NO_MAINTENANCE" in internal:
        progression = [
            float(item["capability"]["operating_flow_m3_s"])
            for item in internal["G80_NO_MAINTENANCE"]
        ]
        if any(
            later > earlier
            for earlier, later in zip(
                progression,
                progression[1:],
                strict=False,
            )
        ):
            raise PipelineReject(
                "qualitative-reject",
                "progression-improvement",
            )


def residual_register() -> list[dict[str, str]]:
    """Return all W3 residual definitions without W4 tolerances."""
    exact_ids = {"C-R16", "C-R20", "C-R24"}
    return [
        {
            "check_id": f"C-R{index:02d}",
            "classification": (
                "exact-satisfied"
                if f"C-R{index:02d}" in exact_ids
                else "observed-pending-w4"
            ),
            "name": name,
        }
        for index, name in enumerate(RESIDUAL_NAMES, start=1)
    ]


def certify(
    segments: tuple[candidate.SegmentInputs, ...],
    authority: dict[str, Any],
    *,
    case_ids: tuple[str, ...] = boundary.W2_CASES,
    require_anchor_witnesses: bool = True,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Run the valid-candidate W3 pipeline and return result-owned evidence."""
    _verify_replay(segments, case_ids)
    _require_ambiguity_request_distinction(segments, case_ids)
    internal: dict[str, list[dict[str, Any]]] = {
        case_id: [] for case_id in case_ids
    }
    result_cases: list[dict[str, Any]] = []
    segment_cursor = 0
    common_member_id: str | None = None
    common_engine: dict[str, Any] | None = None
    last_request: dict[str, Any] | None = None
    for case_id in case_ids:
        expected_count = candidate.SEGMENT_COUNT_BY_CASE[case_id]
        case_segments = segments[
            segment_cursor : segment_cursor + expected_count
        ]
        segment_cursor += expected_count
        result_segments: list[dict[str, Any]] = []
        prior_semantic: dict[str, Any] | None = None
        for segment in case_segments:
            request_value = candidate.read_request(segment.roles["request"])
            last_request = request_value
            if request_value["case"]["case_id"] != case_id:
                raise PipelineReject("exact-reject", "case-role-binding")
            values = physics.validate_member(request_value["member"], authority)
            cases.validate_case(request_value["case"], values)
            if common_member_id is None:
                common_member_id = request_value["member"]["member_content_id"]
                common_engine = request_value["engine"]
            elif (
                request_value["member"]["member_content_id"] != common_member_id
                or request_value["engine"] != common_engine
            ):
                raise PipelineReject(
                    "exact-reject",
                    "catalogue-common-input",
                )
            semantic = candidate.read_semantic(
                segment.roles["semantic-candidate"]
            )
            if semantic["segment_id"] != segment.segment_id:
                raise PipelineReject("exact-reject", "segment-role-binding")
            _exact_sha(semantic["rendered_input_sha256"], "rendered-input-id")
            _curve_evidence(segment, semantic, request_value, values)
            carried_depth = _carry_value(
                prior_semantic,
                semantic,
                case_id=case_id,
                segment_id=segment.segment_id,
            )
            residuals = observations.segment_observations(
                request=request_value,
                semantic=semantic,
                values=values,
                segment_id=segment.segment_id,
                carried_depth=carried_depth,
            )
            capability = _capability(
                request_value,
                values,
                segment.segment_id,
            )
            result_segments.append(
                {
                    "capability": capability,
                    "residuals": residuals,
                    "segment_id": segment.segment_id,
                    "terminal_state": "quantitative-pending-w4",
                }
            )
            internal[case_id].append(
                {
                    "capability": capability,
                    "roles": segment.roles,
                    "semantic": semantic,
                }
            )
            prior_semantic = semantic
        if last_request is None:
            raise PipelineReject("certifier-input-reject", "empty-case")
        result_cases.append(
            {
                "case_content_id": last_request["case"]["case_content_id"],
                "case_id": case_id,
                "segments": result_segments,
                "terminal_state": "quantitative-pending-w4",
            }
        )
    if last_request is None:
        raise PipelineReject("certifier-input-reject", "empty-catalogue")
    _require_relations(
        internal,
        physics.member_values(last_request["member"]),
        require_anchor_witnesses=require_anchor_witnesses,
    )
    checks = [
        {"check_id": check_id, "outcome": "satisfied", "stage": stage}
        for check_id, stage in (
            ("C-REPLAY", "replay-identity"),
            ("C-REQUEST", "canonical-request"),
            ("C-CASE", "case-reconstruction"),
            ("C-CURVE", "curve-reconstruction"),
            ("C-SEMANTIC", "semantic-candidate"),
            ("C-DIAGNOSTIC", "engine-diagnostics"),
            ("C-EXACT", "exact-invariants"),
            ("C-QUALITATIVE", "qualitative-relations"),
        )
    ]
    return result_cases, checks
