# ABOUTME: Evaluates bounded real-engine perturbations against replay, duration, topology, and hydraulic rules.
# ABOUTME: Consumes generated evidence without importing the generator or treating a diagnostic as promotable.

from __future__ import annotations

import hashlib
import json
import math
import struct
from decimal import Decimal
from typing import Any

from sensitivity import anchor, catalogue, physics, tolerances

RESULT_DOMAIN = b"asw-0b5.engine-variant-evaluation.v1\0"
FORCED_CASES = (
    "G12_CLEAN_ASSESS",
    "G21_OBSTRUCTION_TRIGGER",
    "G31_CLEARANCE_UPPER",
    "G41_COMBINED_UPPER",
)


class EngineVariantError(ValueError):
    """Raised when bounded engine evidence cannot be evaluated exactly."""


def _binary32(value: object) -> float:
    if (
        not isinstance(value, str)
        or len(value) != 8
        or value.lower() != value
    ):
        raise EngineVariantError("engine variant binary32 value differs")
    decoded = struct.unpack(">f", bytes.fromhex(value))[0]
    if not math.isfinite(decoded) or value == "80000000":
        raise EngineVariantError("engine variant binary32 value differs")
    return float(decoded)


def _request(case: dict[str, Any]) -> dict[str, Any]:
    raw = case.get("request_bytes")
    if not isinstance(raw, bytes):
        raise EngineVariantError("engine variant request bytes are absent")
    value = json.loads(raw)
    if (
        not isinstance(value, dict)
        or catalogue.canonical_json_bytes(value) != raw
    ):
        raise EngineVariantError("engine variant request is not canonical")
    return value


def _segments(result: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    replays = result.get("replays")
    if not isinstance(replays, list) or len(replays) != 2:
        raise EngineVariantError("engine variant requires two replays")
    replay = replays[0]
    cases = replay.get("cases")
    if not isinstance(cases, dict):
        raise EngineVariantError("engine variant cases are absent")
    indexed = {
        (case_id, segment["segment_id"]): segment
        for case_id, case in cases.items()
        for segment in case["segments"]
    }
    if len(indexed) != sum(
        len(case["segments"]) for case in cases.values()
    ):
        raise EngineVariantError("engine variant segments are not unique")
    return indexed


def _series(
    segment: dict[str, Any],
    identity: str,
) -> list[float | int]:
    values = segment["semantic"]["series"][identity]["values"]
    return [
        value if isinstance(value, int) else _binary32(value)
        for value in values
    ]


def _duration_and_topology(
    result: dict[str, Any],
) -> dict[str, Any]:
    failure = "none"
    evaluated = 0
    cases = result["replays"][0]["cases"]
    for case_id in result["case_ids"]:
        case_result = cases[case_id]
        request = _request(case_result)
        for segment in case_result["segments"]:
            evaluated += 1
            semantic = segment["semantic"]
            times = _series(segment, "time_s")
            pump_a = _series(segment, "pump_a_setting")
            pump_b = _series(segment, "pump_b_setting")
            if not times or times[-1] != segment["period_count"] * (
                semantic["engine_output"]["report_step_seconds"]
            ):
                failure = "engine-variant-duration"
                break
            expected_horizon = (
                60
                if case_id == "G70_TRANSFER"
                else request["case"]["horizon_s"]
            )
            if times[-1] != expected_horizon:
                failure = "engine-variant-duration"
                break
            if (
                len(times) != len(pump_a)
                or len(times) != len(pump_b)
                or any(
                    a not in {0, 1}
                    or b not in {0, 1}
                    or (a == 1 and b == 1)
                    for a, b in zip(pump_a, pump_b, strict=True)
                )
            ):
                failure = "engine-variant-topology"
                break
            selected = request["case"]["selected_pump"]
            if case_id == "G70_TRANSFER":
                selected = (
                    "pump-a"
                    if segment["segment_id"] == "segment-a"
                    else "pump-b"
                )
            if (
                selected == "pump-a"
                and any(pump_b)
                or selected == "pump-b"
                and any(pump_a)
            ):
                failure = "engine-variant-duty-label"
                break
        if failure != "none":
            break
    return {
        "evaluated_segments": evaluated,
        "first_failure": failure,
        "outcome": "pass" if failure == "none" else "reject",
    }


def _qualitative_ordering(
    result: dict[str, Any],
    base: dict[str, Any],
) -> dict[str, Any]:
    indexed = _segments(result)
    base_indexed = _segments(base)
    flows = {
        case_id: float(
            _series(
                indexed[(case_id, "single")],
                "force_main_flow_m3_s",
            )[-1]
        )
        for case_id in FORCED_CASES
    }
    failure = "none"
    if not (
        flows["G12_CLEAN_ASSESS"]
        > flows["G31_CLEARANCE_UPPER"]
        > flows["G21_OBSTRUCTION_TRIGGER"]
        > flows["G41_COMBINED_UPPER"]
        > 0
    ):
        failure = "engine-variant-hydraulic-order"
    settings = _series(
        indexed[("G10_CLEAN_A_BASE", "single")],
        "pump_a_setting",
    )
    base_settings = _series(
        base_indexed[("G10_CLEAN_A_BASE", "single")],
        "pump_a_setting",
    )
    starts = sum(
        value == 1 and (index == 0 or settings[index - 1] == 0)
        for index, value in enumerate(settings)
    )
    base_starts = sum(
        value == 1
        and (index == 0 or base_settings[index - 1] == 0)
        for index, value in enumerate(base_settings)
    )
    if failure == "none" and (starts <= 0 or starts != base_starts):
        failure = "engine-variant-control-order"
    return {
        "automatic_start_count": starts,
        "base_automatic_start_count": base_starts,
        "final_forced_flows_m3_s": {
            case_id: format(value, ".17g")
            for case_id, value in flows.items()
        },
        "first_failure": failure,
        "outcome": "pass" if failure == "none" else "reject",
    }


def _curve_resolution(
    result: dict[str, Any],
    base: dict[str, Any],
) -> dict[str, Any]:
    segments = int(result["configuration"]["curve_segments"])
    if segments == 32:
        return {
            "evaluated": 0,
            "first_failure": "none",
            "maximum_ratio": "0",
            "outcome": "pass",
        }
    indexed = _segments(result)
    base_indexed = _segments(base)
    maximum_ratio = 0.0
    failure = "none"
    for case_id in FORCED_CASES:
        segment = indexed[(case_id, "single")]
        base_segment = base_indexed[(case_id, "single")]
        request_value = _request(
            result["replays"][0]["cases"][case_id]
        )
        values = physics.member_values(request_value["member"])
        state, _selected = anchor._state(
            request_value["case"],
            "single",
        )
        obstruction = float(Decimal(state["obstruction"]))
        clearance = float(Decimal(state["clearance-loss"]))
        flow = float(
            _series(segment, "force_main_flow_m3_s")[-1]
        )
        base_flow = float(
            _series(base_segment, "force_main_flow_m3_s")[-1]
        )
        depth = float(_series(segment, "wet_well_depth_m")[-1])
        base_depth = float(
            _series(base_segment, "wet_well_depth_m")[-1]
        )
        slopes = (
            physics.root_slope(
                values,
                flow_m3_s=flow,
                depth_m=depth,
                obstruction=obstruction,
                clearance_loss=clearance,
            ),
            physics.root_slope(
                values,
                flow_m3_s=base_flow,
                depth_m=base_depth,
                obstruction=obstruction,
                clearance_loss=clearance,
            ),
        )
        slope = min(slopes)
        head_bound = tolerances.outward_sum(
            [
                tolerances.curve_head_bound(
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
                ),
                tolerances.curve_head_bound(
                    head_zero_m=Decimal(str(values["pump.H_0"])),
                    obstruction=Decimal(str(obstruction)),
                    clearance_loss=Decimal(str(clearance)),
                    obstruction_coefficient=Decimal(
                        str(values["mechanism.a_o"])
                    ),
                    clearance_coefficient=Decimal(
                        str(values["mechanism.a_c"])
                    ),
                    segments=segments,
                ),
            ]
        )
        allowance = tolerances.outward_sum(
            [
                tolerances.outward_divide(head_bound, slope),
                tolerances.binary32_bound(flow),
                tolerances.binary32_bound(base_flow),
            ]
        )
        ratio = abs(flow - base_flow) / allowance
        maximum_ratio = max(maximum_ratio, ratio)
        if ratio > 1 and failure == "none":
            failure = "engine-variant-curve-budget"
    return {
        "evaluated": len(FORCED_CASES),
        "first_failure": failure,
        "maximum_ratio": format(maximum_ratio, ".17g"),
        "outcome": "pass" if failure == "none" else "reject",
    }


def _representation_mapping(
    result: dict[str, Any],
    base: dict[str, Any],
) -> dict[str, Any]:
    mapping = result["configuration"]["target_mapping"]
    if mapping == "base":
        return {
            "evaluated_segments": 0,
            "first_failure": "none",
            "outcome": "pass",
        }
    indexed = _segments(result)
    base_indexed = _segments(base)
    failure = "none"
    for key, segment in indexed.items():
        if (
            segment["semantic"]["series"]
            != base_indexed[key]["semantic"]["series"]
        ):
            failure = "engine-variant-mapping-series"
            break
    return {
        "evaluated_segments": len(indexed),
        "first_failure": failure,
        "outcome": "pass" if failure == "none" else "reject",
    }


def _result_id(value: dict[str, Any]) -> str:
    payload = {
        key: child
        for key, child in value.items()
        if key != "result_content_id"
    }
    return hashlib.sha256(
        RESULT_DOMAIN + catalogue.canonical_json_bytes(payload)
    ).hexdigest()


def evaluate(
    *,
    probe_catalogue_bytes: bytes,
    variant_results: dict[str, dict[str, Any]],
    required_variant_ids: tuple[str, ...],
) -> dict[str, Any]:
    """Evaluate an ordered set of declared real-engine diagnostics."""
    declaration = catalogue.read_probe_catalogue(
        probe_catalogue_bytes
    )
    declared = {
        item["variant_id"]: item["configuration"]
        for item in declaration["engine_variants"]
    }
    if (
        not required_variant_ids
        or required_variant_ids[0] != "ENG.00.base"
        or tuple(
            variant_id
            for variant_id in declared
            if variant_id in required_variant_ids
        )
        != required_variant_ids
        or set(variant_results) != set(required_variant_ids)
    ):
        raise EngineVariantError(
            "required engine variant inventory differs"
        )
    base = variant_results["ENG.00.base"]
    evaluations: dict[str, Any] = {}
    first_failure = "none"
    for variant_id in required_variant_ids:
        result = variant_results[variant_id]
        if (
            result.get("configuration") != declared[variant_id]
            or result.get("case_ids") != declaration["engine_case_ids"]
            or not all(result.get("replay", {}).values())
        ):
            raise EngineVariantError(
                f"engine variant evidence differs for {variant_id}"
            )
        checks = {
            "curve_resolution": _curve_resolution(result, base),
            "duration_and_topology": _duration_and_topology(result),
            "qualitative_ordering": _qualitative_ordering(
                result,
                base,
            ),
            "representation_mapping": _representation_mapping(
                result,
                base,
            ),
        }
        variant_failure = next(
            (
                check["first_failure"]
                for check in checks.values()
                if check["outcome"] != "pass"
            ),
            "none",
        )
        if first_failure == "none" and variant_failure != "none":
            first_failure = f"{variant_id}:{variant_failure}"
        evaluations[variant_id] = {
            **checks,
            "first_failure": variant_failure,
            "outcome": (
                "pass" if variant_failure == "none" else "reject"
            ),
        }
    value: dict[str, Any] = {
        "evaluations": evaluations,
        "first_failure": first_failure,
        "profile_id": "AU-NSW-LH-SYN-SPS-v1",
        "promotable": False,
        "result_content_id": "",
        "schema_id": "asw-0b5.engine-variant-evaluation.v1",
        "terminal_state": (
            "engine-variants-pass"
            if first_failure == "none"
            else "engine-variants-reject"
        ),
        "variant_ids": list(required_variant_ids),
    }
    value["result_content_id"] = _result_id(value)
    return value


def evaluation_bytes(value: dict[str, Any]) -> bytes:
    """Return canonical diagnostic evidence after identity checking."""
    if value.get("result_content_id") != _result_id(value):
        raise EngineVariantError(
            "engine variant evaluation identity differs"
        )
    return catalogue.canonical_json_bytes(value)
