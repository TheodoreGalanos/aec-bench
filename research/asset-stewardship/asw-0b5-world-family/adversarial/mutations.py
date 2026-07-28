# ABOUTME: Constructs the thirty declared invalid inputs from one valid real-engine certification bundle.
# ABOUTME: Recomputes only enclosing identities so each mutation reaches its intended first rejecting boundary.

from __future__ import annotations

import hashlib
import json
import math
import struct
from collections.abc import Callable
from copy import deepcopy
from typing import Any, cast

from generator import request
from sensitivity import catalogue, physics, tolerances

MUTATION_IDS = tuple(f"M{index:02d}" for index in range(1, 31))
ROLE_ORDER = (
    "request",
    "pump-a-original-curve",
    "pump-a-engine-curve",
    "pump-b-original-curve",
    "pump-b-engine-curve",
    "semantic-candidate",
)
RESULT_DOMAIN = b"asw-0b5.certifier-result.v1\0"


class MutationError(ValueError):
    """Raised when a valid bundle cannot produce the declared mutations."""


def _bundle(raw: bytes) -> dict[str, Any]:
    value = json.loads(raw)
    if (
        not isinstance(value, dict)
        or catalogue.canonical_json_bytes(value) != raw
    ):
        raise MutationError("mutation source bundle is not canonical")
    return cast(dict[str, Any], value)


def _case(
    value: dict[str, Any],
    replay_index: int,
    case_id: str,
) -> dict[str, Any]:
    cases = value["replays"][replay_index]["cases"]
    matches = [case for case in cases if case["case_id"] == case_id]
    if len(matches) != 1:
        raise MutationError(f"mutation case {case_id} is unavailable")
    return cast(dict[str, Any], matches[0])


def _segment(
    value: dict[str, Any],
    replay_index: int,
    case_id: str,
    segment_id: str,
) -> dict[str, Any]:
    case = _case(value, replay_index, case_id)
    matches = [
        segment
        for segment in case["segments"]
        if segment["segment_id"] == segment_id
    ]
    if len(matches) != 1:
        raise MutationError(
            f"mutation segment {case_id}/{segment_id} is unavailable"
        )
    return cast(dict[str, Any], matches[0])


def _role(segment: dict[str, Any], role_id: str) -> dict[str, str]:
    matches = [
        role
        for role in segment["roles"]
        if role["role"] == role_id
    ]
    if len(matches) != 1:
        raise MutationError(f"mutation role {role_id} is unavailable")
    return cast(dict[str, str], matches[0])


def _replace_role(role: dict[str, str], raw: bytes) -> None:
    role["bytes_hex"] = raw.hex()
    role["sha256"] = hashlib.sha256(raw).hexdigest()


def _rewrite_json_role(
    value: dict[str, Any],
    *,
    case_id: str,
    role_id: str,
    mutate: Callable[[dict[str, Any]], None],
    segment_id: str = "single",
) -> None:
    for replay_index in range(2):
        role = _role(
            _segment(
                value,
                replay_index,
                case_id,
                segment_id,
            ),
            role_id,
        )
        child = json.loads(bytes.fromhex(role["bytes_hex"]))
        mutate(child)
        _replace_role(role, request.canonical_json_bytes(child))


def _rewrite_raw_role(
    value: dict[str, Any],
    *,
    case_id: str,
    role_id: str,
    mutate: Callable[[bytes], bytes],
    segment_id: str = "single",
) -> None:
    for replay_index in range(2):
        role = _role(
            _segment(
                value,
                replay_index,
                case_id,
                segment_id,
            ),
            role_id,
        )
        _replace_role(
            role,
            mutate(bytes.fromhex(role["bytes_hex"])),
        )


def _rewrite_case_request(
    value: dict[str, Any],
    *,
    case_id: str,
    mutate: Callable[[dict[str, Any]], None],
) -> None:
    for replay_index in range(2):
        case = _case(value, replay_index, case_id)
        for segment in case["segments"]:
            request_role = _role(segment, "request")
            request_value = json.loads(
                bytes.fromhex(request_role["bytes_hex"])
            )
            mutate(request_value["case"])
            request_value["case"]["case_content_id"] = (
                request.case_content_id(request_value["case"])
            )
            request_value["request_content_id"] = (
                request.request_content_id(request_value)
            )
            _replace_role(
                request_role,
                request.canonical_json_bytes(request_value),
            )
            semantic_role = _role(segment, "semantic-candidate")
            semantic = json.loads(
                bytes.fromhex(semantic_role["bytes_hex"])
            )
            semantic["case_content_id"] = request_value["case"][
                "case_content_id"
            ]
            _replace_role(
                semantic_role,
                request.canonical_json_bytes(semantic),
            )


def _float32(value: float) -> float:
    return float(struct.unpack(">f", struct.pack(">f", value))[0])


def _float32_hex(value: float) -> str:
    return struct.pack(">f", value).hex()


def _decode_float32(value: str) -> float:
    return float(struct.unpack(">f", bytes.fromhex(value))[0])


def _next_float32(value: float, direction: float) -> float:
    bits = int.from_bytes(struct.pack(">f", value), "big")
    if value < direction:
        bits += 1
    else:
        bits -= 1
    return float(struct.unpack(">f", bits.to_bytes(4, "big"))[0])


def _trace_identity(semantic: dict[str, Any]) -> str:
    series = semantic["series"]
    return hashlib.sha256(
        request.canonical_json_bytes(
            {
                "pump_a": series["pump_a_setting"]["values"],
                "pump_b": series["pump_b_setting"]["values"],
            }
        )
    ).hexdigest()


def _m01(value: dict[str, Any]) -> None:
    role = _role(
        _segment(value, 0, "G00_ZERO_STATIC", "single"),
        "semantic-candidate",
    )
    raw = bytearray(bytes.fromhex(role["bytes_hex"]))
    raw[0] ^= 1
    role["bytes_hex"] = bytes(raw).hex()


def _m02(value: dict[str, Any]) -> None:
    _rewrite_json_role(
        value,
        case_id="G00_ZERO_STATIC",
        role_id="semantic-candidate",
        mutate=lambda semantic: semantic.update(
            {"unknown_mutation_field": True}
        ),
    )


def _m03(value: dict[str, Any]) -> None:
    def duplicate(raw: bytes) -> bytes:
        if not raw.endswith(b"}\n"):
            raise MutationError("semantic object terminator differs")
        return raw[:-2] + b',\"status\":\"candidate-only\"}\\n'

    _rewrite_raw_role(
        value,
        case_id="G00_ZERO_STATIC",
        role_id="semantic-candidate",
        mutate=duplicate,
    )


def _m04(value: dict[str, Any]) -> None:
    def exponent(raw: bytes) -> bytes:
        mutated = raw.replace(
            b'"period_count":3600',
            b'"period_count":36e2',
            1,
        )
        if mutated == raw:
            raise MutationError("period count token is unavailable")
        return mutated

    _rewrite_raw_role(
        value,
        case_id="G00_ZERO_STATIC",
        role_id="semantic-candidate",
        mutate=exponent,
    )


def _m05(value: dict[str, Any]) -> None:
    def mutate(semantic: dict[str, Any]) -> None:
        values = semantic["series"]["wet_well_depth_m"]["values"]
        values[0] = values[0].upper()

    _rewrite_json_role(
        value,
        case_id="G00_ZERO_STATIC",
        role_id="semantic-candidate",
        mutate=mutate,
    )


def _m06(value: dict[str, Any]) -> None:
    _rewrite_json_role(
        value,
        case_id="G00_ZERO_STATIC",
        role_id="semantic-candidate",
        mutate=lambda semantic: semantic["series"][
            "wet_well_depth_m"
        ].update({"unit": "mm"}),
    )


def _m07(value: dict[str, Any]) -> None:
    _rewrite_json_role(
        value,
        case_id="G00_ZERO_STATIC",
        role_id="semantic-candidate",
        mutate=lambda semantic: semantic["series"]["time_s"][
            "values"
        ].pop(),
    )


def _m08(value: dict[str, Any]) -> None:
    _rewrite_json_role(
        value,
        case_id="G00_ZERO_STATIC",
        role_id="semantic-candidate",
        mutate=lambda semantic: semantic["series"].pop(
            "discharge_head_m"
        ),
    )


def _m09(value: dict[str, Any]) -> None:
    def mutate(curve: dict[str, Any]) -> None:
        curve["points"].pop()
        curve["point_count"] = 32

    _rewrite_json_role(
        value,
        case_id="G21_OBSTRUCTION_TRIGGER",
        role_id="pump-a-engine-curve",
        mutate=mutate,
    )


def _m10(value: dict[str, Any]) -> None:
    _rewrite_json_role(
        value,
        case_id="G21_OBSTRUCTION_TRIGGER",
        role_id="pump-a-engine-curve",
        mutate=lambda curve: curve["points"][0].update(
            {"head_m": "0.000000001"}
        ),
    )


def _m11(value: dict[str, Any]) -> None:
    def mutate(curve: dict[str, Any]) -> None:
        curve["points"][1], curve["points"][2] = (
            curve["points"][2],
            curve["points"][1],
        )

    _rewrite_json_role(
        value,
        case_id="G21_OBSTRUCTION_TRIGGER",
        role_id="pump-a-engine-curve",
        mutate=mutate,
    )


def _m12(value: dict[str, Any]) -> None:
    def mutate(curve: dict[str, Any]) -> None:
        current = float(curve["points"][1]["head_m"])
        curve["points"][1]["head_m"] = format(
            current + 0.000000001,
            ".9f",
        )

    _rewrite_json_role(
        value,
        case_id="G10_CLEAN_A_BASE",
        role_id="pump-b-engine-curve",
        mutate=mutate,
    )


def _m13(value: dict[str, Any]) -> None:
    def mutate(semantic: dict[str, Any]) -> None:
        semantic["series"]["pump_a_setting"]["values"][0] = 1
        semantic["series"]["pump_b_setting"]["values"][0] = 1
        semantic["setting_trace_sha256"] = _trace_identity(semantic)

    _rewrite_json_role(
        value,
        case_id="G00_ZERO_STATIC",
        role_id="semantic-candidate",
        mutate=mutate,
    )


def _m14(value: dict[str, Any]) -> None:
    def mutate(semantic: dict[str, Any]) -> None:
        series = semantic["series"]
        series["pump_a_setting"], series["pump_b_setting"] = (
            series["pump_b_setting"],
            series["pump_a_setting"],
        )
        series["pump_a_flow_m3_s"], series["pump_b_flow_m3_s"] = (
            series["pump_b_flow_m3_s"],
            series["pump_a_flow_m3_s"],
        )
        semantic["setting_trace_sha256"] = _trace_identity(semantic)

    _rewrite_json_role(
        value,
        case_id="G12_CLEAN_ASSESS",
        role_id="semantic-candidate",
        mutate=mutate,
    )


def _m15(value: dict[str, Any]) -> None:
    def mutate(semantic: dict[str, Any]) -> None:
        series = semantic["series"]
        force = _decode_float32(
            series["force_main_flow_m3_s"]["values"][0]
        )
        off_flow = _float32(1e-9)
        active_flow = _float32(force - off_flow)
        combined = _float32(active_flow + off_flow)
        series["pump_a_flow_m3_s"]["values"][0] = _float32_hex(
            active_flow
        )
        series["pump_b_flow_m3_s"]["values"][0] = _float32_hex(
            off_flow
        )
        series["force_main_flow_m3_s"]["values"][0] = _float32_hex(
            combined
        )

    _rewrite_json_role(
        value,
        case_id="G12_CLEAN_ASSESS",
        role_id="semantic-candidate",
        mutate=mutate,
    )


def _m16(value: dict[str, Any]) -> None:
    def mutate(semantic: dict[str, Any]) -> None:
        series = semantic["series"]
        depth = _decode_float32(
            series["wet_well_depth_m"]["values"][0]
        )
        volume = _decode_float32(
            series["wet_well_volume_m3"]["values"][0]
        )
        request_value = json.loads(
            bytes.fromhex(
                _role(
                    _segment(
                        value,
                        0,
                        "G00_ZERO_STATIC",
                        "single",
                    ),
                    "request",
                )["bytes_hex"]
            )
        )
        values = physics.member_values(request_value["member"])
        area = physics.wet_well_area(values)
        area_bound = (
            math.pi
            / 2
            * abs(values["well.D_w"])
            * 0.5e-9
            + math.pi / 4 * (0.5e-9) ** 2
        )
        candidate = volume
        for _ in range(1000):
            candidate = _next_float32(candidate, math.inf)
            budget = tolerances.outward_sum(
                [
                    tolerances.binary32_bound(candidate),
                    area * tolerances.binary32_bound(depth),
                    abs(depth) * area_bound,
                    area_bound * tolerances.binary32_bound(depth),
                    tolerances.binary64_guard(candidate),
                ]
            )
            if abs(candidate - area * depth) > budget:
                series["wet_well_volume_m3"]["values"][0] = (
                    _float32_hex(candidate)
                )
                return
        raise MutationError("minimum storage mutation was not found")

    _rewrite_json_role(
        value,
        case_id="G00_ZERO_STATIC",
        role_id="semantic-candidate",
        mutate=mutate,
    )


def _m17(value: dict[str, Any]) -> None:
    def mutate(semantic: dict[str, Any]) -> None:
        series = semantic["series"]
        index = 43
        active = _decode_float32(
            series["pump_a_flow_m3_s"]["values"][index]
        )
        delta = _float32(0.000005)
        changed = _float32(active - delta)
        series["pump_a_flow_m3_s"]["values"][index] = _float32_hex(
            changed
        )
        series["force_main_flow_m3_s"]["values"][index] = _float32_hex(
            changed
        )

    _rewrite_json_role(
        value,
        case_id="G12_CLEAN_ASSESS",
        role_id="semantic-candidate",
        mutate=mutate,
    )


def _m19(value: dict[str, Any]) -> None:
    _rewrite_case_request(
        value,
        case_id="G21_OBSTRUCTION_TRIGGER",
        mutate=lambda case: case["mechanism_state"]["pump-a"].update(
            {"obstruction": "0.50"}
        ),
    )


def _m20(value: dict[str, Any]) -> None:
    _rewrite_case_request(
        value,
        case_id="G51_CLEAR_A_POST",
        mutate=lambda case: case.update({"history_retained": False}),
    )


def _m21(value: dict[str, Any]) -> None:
    _rewrite_case_request(
        value,
        case_id="G51_CLEAR_A_POST",
        mutate=lambda case: case["mechanism_state"]["pump-a"].update(
            {"clearance-loss": "0.05"}
        ),
    )


def _m22(value: dict[str, Any]) -> None:
    _rewrite_case_request(
        value,
        case_id="G61_REPAIR_POST",
        mutate=lambda case: case["mechanism_state"]["pump-a"].update(
            {"obstruction": "0.25"}
        ),
    )


def _m23(value: dict[str, Any]) -> None:
    def mutate(semantic: dict[str, Any]) -> None:
        semantic["carry"][0]["value"] = "00000000"

    _rewrite_json_role(
        value,
        case_id="G70_TRANSFER",
        segment_id="segment-b",
        role_id="semantic-candidate",
        mutate=mutate,
    )


def _m24(value: dict[str, Any]) -> None:
    def mutate(case: dict[str, Any]) -> None:
        case["exposure_state"]["pump-b"]["runtime_s"] = 1

    _rewrite_case_request(
        value,
        case_id="G70_TRANSFER",
        mutate=mutate,
    )


def _m25(value: dict[str, Any]) -> None:
    def mutate(case: dict[str, Any]) -> None:
        transition = deepcopy(case["physical_transitions"][0])
        transition["effective_second"] = 90
        case["physical_transitions"].append(transition)

    _rewrite_case_request(
        value,
        case_id="G70_TRANSFER",
        mutate=mutate,
    )


def _m26(value: dict[str, Any]) -> None:
    def mutate(case: dict[str, Any]) -> None:
        case["mechanism_state"]["pump-a"] = {
            "clearance-loss": "0.10",
            "obstruction": "0.0975",
        }

    _rewrite_case_request(
        value,
        case_id="G53_CLEAR_B_POST",
        mutate=mutate,
    )


def _m27(value: dict[str, Any]) -> None:
    def mutate(semantic: dict[str, Any]) -> None:
        series = semantic["series"]
        depth = _decode_float32(
            series["wet_well_depth_m"]["values"][0]
        )
        changed = _next_float32(depth, math.inf)
        encoded = _float32_hex(changed)
        series["wet_well_depth_m"]["values"][0] = encoded
        series["wet_well_head_m"]["values"][0] = encoded

    _rewrite_json_role(
        value,
        case_id="G11_CLEAN_B_BASE",
        role_id="semantic-candidate",
        mutate=mutate,
    )


def _m28(value: dict[str, Any]) -> None:
    _rewrite_json_role(
        value,
        case_id="G00_ZERO_STATIC",
        role_id="semantic-candidate",
        mutate=lambda semantic: semantic["diagnostics"].update(
            {"warnings": ["mutation-warning"]}
        ),
    )


def _m29(value: dict[str, Any]) -> None:
    _rewrite_json_role(
        value,
        case_id="G00_ZERO_STATIC",
        role_id="semantic-candidate",
        mutate=lambda semantic: semantic.update({"promotable": True}),
    )


def _m30(value: dict[str, Any]) -> None:
    _rewrite_json_role(
        value,
        case_id="G00_ZERO_STATIC",
        role_id="semantic-candidate",
        mutate=lambda semantic: semantic.update(
            {"maintenance_action": "forbidden"}
        ),
    )


MUTATORS: dict[str, Callable[[dict[str, Any]], None]] = {
    "M01": _m01,
    "M02": _m02,
    "M03": _m03,
    "M04": _m04,
    "M05": _m05,
    "M06": _m06,
    "M07": _m07,
    "M08": _m08,
    "M09": _m09,
    "M10": _m10,
    "M11": _m11,
    "M12": _m12,
    "M13": _m13,
    "M14": _m14,
    "M15": _m15,
    "M16": _m16,
    "M17": _m17,
    "M19": _m19,
    "M20": _m20,
    "M21": _m21,
    "M22": _m22,
    "M23": _m23,
    "M24": _m24,
    "M25": _m25,
    "M26": _m26,
    "M27": _m27,
    "M28": _m28,
    "M29": _m29,
    "M30": _m30,
}


def build_bundle_mutations(bundle_bytes: bytes) -> dict[str, bytes]:
    """Build every bundle-owned invalid input in declared order."""
    results: dict[str, bytes] = {}
    for mutation_id in MUTATION_IDS:
        mutator = MUTATORS.get(mutation_id)
        if mutator is None:
            continue
        value = _bundle(bundle_bytes)
        mutator(value)
        results[mutation_id] = request.canonical_json_bytes(value)
    return results


def _result_id(value: dict[str, Any]) -> str:
    payload = {
        key: child
        for key, child in value.items()
        if key != "result_content_id"
    }
    return hashlib.sha256(
        RESULT_DOMAIN + catalogue.canonical_json_bytes(payload)
    ).hexdigest()


def build_result_mutations(
    certifier_result_bytes: bytes,
) -> dict[str, bytes]:
    """Build the W4-owned mutation of valid certifier evidence."""
    source = json.loads(certifier_result_bytes)
    if catalogue.canonical_json_bytes(source) != certifier_result_bytes:
        raise MutationError(
            "mutation source certifier result is not canonical"
        )
    results: dict[str, bytes] = {}

    capacity = deepcopy(source)
    changed = False
    for case in capacity["cases"]:
        for segment in case["segments"]:
            record = segment["residuals"]["C-R09"]
            if record["sample_count"] > 0:
                record["minimum_reynolds_margin"] = "-0.0000000000000001"
                changed = True
                break
        if changed:
            break
    if not changed:
        raise MutationError("C-R09 mutation target is unavailable")
    capacity["result_content_id"] = _result_id(capacity)
    results["M18"] = catalogue.canonical_json_bytes(capacity)

    return results
