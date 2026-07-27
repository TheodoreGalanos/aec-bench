# ABOUTME: Independently parses W3 transfer envelopes, requests, curves, and semantic candidate bytes.
# ABOUTME: Recomputes hashes and binary32 values without generator, SWMM, raw engine artifacts, or shared helpers.

from __future__ import annotations

import hashlib
import math
import re
import struct
from dataclasses import dataclass
from typing import Any, NoReturn, cast

from certifier import boundary

PROFILE_ID = "AU-NSW-LH-SYN-SPS-v1"
PROTOCOL_ID = "asw-0b5.generator-protocol.v3"
REPAIR_SHA256 = "862ef1f5fc70d882d156c0ef9842bb565301344725d2206edfa49c10910576ca"
BUNDLE_SCHEMA_ID = "asw-0b5.certifier-input-bundle.v1"
REQUEST_SCHEMA_ID = "asw-0b5.generator-request.v1"
SEMANTIC_SCHEMA_ID = "asw-0b5.semantic-output.v1"
SEMANTIC_DOMAIN = b"asw-0b4.semantic-output.v1\0"
MEMBER_DOMAIN = b"asw-0b4.member.v1\0"
CASE_DOMAIN = b"asw-0b4.case.v1\0"
REQUEST_DOMAIN = b"asw-0b4.generator-request.v1\0"
BINARY32_PATTERN = re.compile(r"[0-9a-f]{8}\Z")
HEX_BYTES_PATTERN = re.compile(r"(?:[0-9a-f]{2})+\Z")
SERIES_IDS = (
    "time_s",
    "wet_well_depth_m",
    "wet_well_volume_m3",
    "wet_well_inflow_m3_s",
    "wet_well_overflow_m3_s",
    "pump_a_flow_m3_s",
    "pump_b_flow_m3_s",
    "force_main_flow_m3_s",
    "pump_a_setting",
    "pump_b_setting",
    "wet_well_head_m",
    "discharge_head_m",
)
ROLE_IDS = (
    "request",
    "pump-a-original-curve",
    "pump-a-engine-curve",
    "pump-b-original-curve",
    "pump-b-engine-curve",
    "semantic-candidate",
)
SEGMENT_COUNT_BY_CASE = {
    **{case_id: 1 for case_id in boundary.W2_CASES},
    "G70_TRANSFER": 2,
    "G80_NO_MAINTENANCE": 4,
}


class CandidateError(ValueError):
    """Deterministic W3 candidate rejection."""

    def __init__(self, stage: str, detail: str) -> None:
        self.stage = stage
        super().__init__(f"certifier-candidate:{stage}: {detail}")


def _reject(stage: str, detail: str) -> NoReturn:
    raise CandidateError(stage, detail)


@dataclass(frozen=True)
class SegmentInputs:
    """One segment's exact permitted W3 byte roles."""

    case_id: str
    replay_ordinal: int
    roles: dict[str, bytes]
    segment_id: str


def _parse(raw: bytes, stage: str) -> dict[str, Any]:
    try:
        return boundary._parse_canonical_object(raw)
    except boundary.CertifierBoundaryError as error:
        _reject(stage, str(error))


def _exact_keys(
    value: object,
    expected: set[str],
    stage: str,
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != expected:
        _reject(stage, f"expected keys {sorted(expected)!r}")
    return cast(dict[str, Any], value)


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _decode_role(value: object, expected_role: str) -> bytes:
    role = _exact_keys(
        value,
        {"bytes_hex", "role", "sha256"},
        "bundle-role",
    )
    if role["role"] != expected_role:
        _reject("bundle-role", f"expected role {expected_role!r}")
    encoded = role["bytes_hex"]
    if not isinstance(encoded, str) or HEX_BYTES_PATTERN.fullmatch(encoded) is None:
        _reject("bundle-role", "role bytes are not canonical lower-case hex")
    raw = bytes.fromhex(encoded)
    if role["sha256"] != _sha256(raw):
        _reject("bundle-role", f"content hash differs for {expected_role}")
    return raw


def read_bundle(raw: bytes) -> tuple[SegmentInputs, ...]:
    """Read the exact two-replay path-free W3 transfer envelope."""
    bundle = _parse(raw, "bundle-bytes")
    _exact_keys(
        bundle,
        {"profile_id", "promotable", "replays", "schema_id"},
        "bundle-shape",
    )
    if (
        bundle["schema_id"] != BUNDLE_SCHEMA_ID
        or bundle["profile_id"] != PROFILE_ID
        or bundle["promotable"] is not False
    ):
        _reject("bundle-authority", "bundle authority or maturity differs")
    replays = bundle["replays"]
    if not isinstance(replays, list) or len(replays) != 2:
        _reject("bundle-shape", "exactly two replays are required")
    collected: list[SegmentInputs] = []
    for ordinal, replay_value in enumerate(replays):
        replay = _exact_keys(replay_value, {"cases", "ordinal"}, "bundle-replay")
        if replay["ordinal"] != ordinal:
            _reject("bundle-replay", "replay ordinal differs")
        cases = replay["cases"]
        if not isinstance(cases, list) or len(cases) != len(boundary.W2_CASES):
            _reject("bundle-case", "case inventory differs")
        for case_id, case_value in zip(boundary.W2_CASES, cases, strict=True):
            case = _exact_keys(case_value, {"case_id", "segments"}, "bundle-case")
            if case["case_id"] != case_id:
                _reject("bundle-case", f"expected {case_id}")
            segments = case["segments"]
            expected_count = SEGMENT_COUNT_BY_CASE[case_id]
            if not isinstance(segments, list) or len(segments) != expected_count:
                _reject("bundle-segment", f"segment count differs for {case_id}")
            expected_ids = (
                ("segment-a", "segment-b")
                if case_id == "G70_TRANSFER"
                else (
                    tuple(f"checkpoint-{index}" for index in range(4))
                    if case_id == "G80_NO_MAINTENANCE"
                    else ("single",)
                )
            )
            for segment_id, segment_value in zip(expected_ids, segments, strict=True):
                segment = _exact_keys(
                    segment_value,
                    {"roles", "segment_id"},
                    "bundle-segment",
                )
                if segment["segment_id"] != segment_id:
                    _reject("bundle-segment", f"expected segment {segment_id}")
                roles = segment["roles"]
                if not isinstance(roles, list) or len(roles) != len(ROLE_IDS):
                    _reject("bundle-role", "role cardinality differs")
                decoded = {
                    role_id: _decode_role(role_value, role_id)
                    for role_id, role_value in zip(ROLE_IDS, roles, strict=True)
                }
                collected.append(
                    SegmentInputs(
                        case_id=case_id,
                        replay_ordinal=ordinal,
                        roles=decoded,
                        segment_id=segment_id,
                    )
                )
    if len(collected) != 46:
        _reject("bundle-segment", "complete bundle must contain 46 segments")
    return tuple(collected)


def _content_id(domain: bytes, value: dict[str, Any], identity_field: str) -> str:
    without_identity = {
        key: child for key, child in value.items() if key != identity_field
    }
    return hashlib.sha256(
        domain + boundary.canonical_json_bytes(without_identity)
    ).hexdigest()


def read_request(raw: bytes) -> dict[str, Any]:
    """Independently parse and identity-check one canonical W2 request."""
    value = _parse(raw, "request-bytes")
    _exact_keys(
        value,
        {
            "authority",
            "case",
            "engine",
            "member",
            "outputs",
            "request_content_id",
            "schema_id",
        },
        "request-shape",
    )
    if value["schema_id"] != REQUEST_SCHEMA_ID or value["outputs"] != list(SERIES_IDS):
        _reject("request-shape", "schema or output allowlist differs")
    authority = value["authority"]
    expected_authority = {
        "profile_id": PROFILE_ID,
        "promotable": False,
        "protocol_id": PROTOCOL_ID,
        "repair_declaration_sha256": REPAIR_SHA256,
        "scope": "research-only",
        "w1_declaration_sha256": boundary.REVIEWED_W1_DECLARATION,
        "w1_sha256": dict(boundary.AUTHORITIES)["w1"],
    }
    if authority != expected_authority:
        _reject("request-authority", "request authority differs")
    member = _exact_keys(
        value["member"],
        {"composites", "member_content_id", "parameters"},
        "request-member",
    )
    case = value["case"]
    if not isinstance(case, dict):
        _reject("request-case", "case must be an object")
    typed_case = cast(dict[str, Any], case)
    if member["member_content_id"] != _content_id(
        MEMBER_DOMAIN,
        member,
        "member_content_id",
    ):
        _reject("request-identity", "member content identity differs")
    if typed_case.get("case_content_id") != _content_id(
        CASE_DOMAIN,
        typed_case,
        "case_content_id",
    ):
        _reject("request-identity", "case content identity differs")
    if value["request_content_id"] != _content_id(
        REQUEST_DOMAIN,
        value,
        "request_content_id",
    ):
        _reject("request-identity", "request content identity differs")
    engine_value = _exact_keys(
        value["engine"],
        {
            "build_receipt_sha256",
            "commit",
            "executable_sha256",
            "output_library_sha256",
            "patch_sha256",
            "repository",
            "settings_id",
            "solver_library_sha256",
            "version",
        },
        "request-engine",
    )
    if (
        engine_value["commit"] != "7952ca837988b1c32f791812eccc9fd64547e093"
        or engine_value["repository"]
        != "https://github.com/USEPA/Stormwater-Management-Model.git"
        or engine_value["settings_id"] != "asw-0b5.swmm-settings.v2"
        or engine_value["version"] != "5.2.4"
    ):
        _reject("request-engine", "engine identity differs")
    for field in (
        "build_receipt_sha256",
        "executable_sha256",
        "output_library_sha256",
        "patch_sha256",
        "solver_library_sha256",
    ):
        if (
            not isinstance(engine_value[field], str)
            or boundary.LOWER_SHA256.fullmatch(engine_value[field]) is None
        ):
            _reject("request-engine", f"{field} is not a SHA-256")
    return value


def read_curve(raw: bytes, representation: str) -> dict[str, Any]:
    """Parse one exact canonical original or repaired engine curve."""
    value = _parse(raw, "curve-bytes")
    _exact_keys(value, {"point_count", "points", "representation"}, "curve-shape")
    if value["representation"] != representation or value["point_count"] != 33:
        _reject("curve-shape", "curve representation or point count differs")
    points = value["points"]
    if not isinstance(points, list) or len(points) != 33:
        _reject("curve-shape", "curve point inventory differs")
    previous_head: float | None = None
    previous_flow: float | None = None
    for point_value in points:
        point = _exact_keys(point_value, {"flow_lps", "head_m"}, "curve-point")
        try:
            head = float(point["head_m"])
            flow = float(point["flow_lps"])
        except (TypeError, ValueError):
            _reject("curve-point", "curve point scalar differs")
        if not math.isfinite(head) or not math.isfinite(flow) or head < 0 or flow < 0:
            _reject("curve-point", "curve point must be finite and non-negative")
        if previous_head is not None and head <= previous_head:
            _reject("curve-order", "curve head is not strictly increasing")
        if previous_flow is not None and flow > previous_flow:
            _reject("curve-order", "curve flow increases")
        previous_head = head
        previous_flow = flow
    first = cast(dict[str, str], points[0])
    last = cast(dict[str, str], points[-1])
    if first["head_m"] != "0.000000000" or last["flow_lps"] != "0.000000":
        _reject("curve-endpoint", "curve zero endpoint differs")
    return value


def decode_binary32(value: str) -> float:
    """Decode one canonical W2 binary32 without decimal round-tripping."""
    if BINARY32_PATTERN.fullmatch(value) is None:
        _reject("semantic-binary32", "binary32 value is not eight lower-case hex digits")
    if value == "80000000":
        _reject("semantic-binary32", "negative zero is non-canonical")
    decoded = float(struct.unpack(">f", bytes.fromhex(value))[0])
    if not math.isfinite(decoded):
        _reject("semantic-binary32", "binary32 value must be finite")
    return decoded


def semantic_sha256(value: dict[str, Any]) -> str:
    """Independently compute the domain-separated semantic output identity."""
    return hashlib.sha256(
        SEMANTIC_DOMAIN + boundary.canonical_json_bytes(value)
    ).hexdigest()


def read_semantic(raw: bytes) -> dict[str, Any]:
    """Parse exact W2 semantic bytes and independently decode every series."""
    value = _parse(raw, "semantic-bytes")
    _exact_keys(
        value,
        {
            "authority",
            "carry",
            "case_content_id",
            "curve_evidence",
            "diagnostics",
            "engine",
            "engine_output",
            "lifecycle_return_codes",
            "member_content_id",
            "period_count",
            "promotable",
            "rendered_input_sha256",
            "schema_id",
            "segment_id",
            "series",
            "setting_trace_sha256",
            "status",
        },
        "semantic-shape",
    )
    if (
        value["schema_id"] != SEMANTIC_SCHEMA_ID
        or value["status"] != "candidate-only"
        or value["promotable"] is not False
    ):
        _reject("semantic-maturity", "semantic maturity boundary differs")
    period_count = value["period_count"]
    if isinstance(period_count, bool) or not isinstance(period_count, int) or period_count <= 0:
        _reject("semantic-period", "period count must be a positive integer")
    series = value["series"]
    if not isinstance(series, dict) or set(series) != set(SERIES_IDS):
        _reject("semantic-series", "semantic series inventory differs")
    binary_units = {
        "wet_well_depth_m": "m",
        "wet_well_volume_m3": "m³",
        "wet_well_inflow_m3_s": "m³/s",
        "wet_well_overflow_m3_s": "m³/s",
        "pump_a_flow_m3_s": "m³/s",
        "pump_b_flow_m3_s": "m³/s",
        "force_main_flow_m3_s": "m³/s",
        "wet_well_head_m": "m",
        "discharge_head_m": "m",
    }
    for identity in SERIES_IDS:
        series_value = series[identity]
        if not isinstance(series_value, dict):
            _reject("semantic-series", f"{identity} is not an object")
        values = series_value.get("values")
        if not isinstance(values, list) or len(values) != period_count:
            _reject("semantic-period", f"{identity} length differs")
        if identity in {"time_s", "pump_a_setting", "pump_b_setting"}:
            if set(series_value) != {"representation", "source", "unit", "values"}:
                _reject("semantic-series", f"{identity} shape differs")
            if series_value["representation"] != "exact-integer":
                _reject("semantic-series", f"{identity} representation differs")
            if any(isinstance(item, bool) or not isinstance(item, int) for item in values):
                _reject("semantic-series", f"{identity} contains non-integer values")
        else:
            expected_keys = {"representation", "source", "unit", "values"}
            if identity in {
                "wet_well_inflow_m3_s",
                "wet_well_overflow_m3_s",
                "pump_a_flow_m3_s",
                "pump_b_flow_m3_s",
            }:
                expected_keys.add("transformation")
                if series_value.get("transformation") != (
                    "asw-0b4.exact-scale.lps-to-m3-s.v1"
                ):
                    _reject("semantic-series", f"{identity} transformation differs")
            if set(series_value) != expected_keys:
                _reject("semantic-series", f"{identity} shape differs")
            if (
                series_value["representation"] != "ieee754-binary32-be-hex"
                or series_value["unit"] != binary_units[identity]
            ):
                _reject("semantic-series", f"{identity} representation or unit differs")
            for item in values:
                if not isinstance(item, str):
                    _reject("semantic-binary32", f"{identity} value is not text")
                decode_binary32(item)
    time_values = series["time_s"]["values"]
    if series["time_s"]["unit"] != "s" or time_values != list(
        range(1, period_count + 1)
    ):
        _reject("semantic-time", "time grid differs")
    for setting_id in ("pump_a_setting", "pump_b_setting"):
        if series[setting_id]["unit"] != "1" or any(
            item not in {0, 1} for item in series[setting_id]["values"]
        ):
            _reject("semantic-setting", f"{setting_id} domain differs")
    return value
