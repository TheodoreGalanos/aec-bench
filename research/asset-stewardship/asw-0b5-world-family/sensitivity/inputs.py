# ABOUTME: Parses W4 transfer inputs with sensitivity-owned canonical and replay checks.
# ABOUTME: Recomputes every role hash without importing generator or certifier readers.

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, NoReturn, cast

from sensitivity import catalogue

ROLE_IDS = (
    "request",
    "pump-a-original-curve",
    "pump-a-engine-curve",
    "pump-b-original-curve",
    "pump-b-engine-curve",
    "semantic-candidate",
)
W1_PROTOCOL_SHA256 = "337aeab9465a8a1801b67c2ab0b408a2a2f07becddffc4a02161b64e6a8630de"
W3_PROTOCOL_SHA256 = "2b0b13a6f9facaf2f0e18f19a5d41069d8e5708a2df77b6dc6d6ed6c9ec65cde"
CERTIFIER_RESULT_DOMAIN = b"asw-0b5.certifier-result.v1\0"
LOWER_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
LOWER_HEX = re.compile(r"(?:[0-9a-f]{2})+\Z")


class SensitivityInputError(ValueError):
    """Fail-closed W4 transfer or certifier-result input error."""


@dataclass(frozen=True)
class SegmentEvidence:
    """One first-replay segment with exact role bytes and parsed W4 inputs."""

    case_id: str
    request: dict[str, Any]
    role_bytes: dict[str, bytes]
    role_sha256: dict[str, str]
    segment_id: str
    semantic: dict[str, Any]


@dataclass(frozen=True)
class CertifierEvidence:
    """One independently identified W3 result bound to exact W2 transfer bytes."""

    result_content_id: str
    segment_results: dict[tuple[str, str], dict[str, Any]]
    terminal_state: str
    value: dict[str, Any]


def _fail(detail: str) -> NoReturn:
    raise SensitivityInputError(f"w4-input: {detail}")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            _fail(f"duplicate key {key!r}")
        result[key] = value
    return result


def read_canonical_object(raw: bytes) -> dict[str, Any]:
    """Read one canonical JSON object with W4-owned duplicate-key rejection."""
    if not raw.endswith(b"\n") or raw.endswith(b"\n\n") or b"\r" in raw:
        _fail("exactly one terminal LF is required")
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_unique_object,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        _fail(str(error))
    if not isinstance(value, dict):
        _fail("top-level value must be an object")
    parsed = cast(dict[str, Any], value)
    if catalogue.canonical_json_bytes(parsed) != raw:
        _fail("bytes are not canonical")
    return parsed


def _decoded_roles(segment: dict[str, Any]) -> tuple[dict[str, bytes], dict[str, str]]:
    roles = segment.get("roles")
    if not isinstance(roles, list) or len(roles) != len(ROLE_IDS):
        _fail("role inventory differs")
    decoded: dict[str, bytes] = {}
    identities: dict[str, str] = {}
    for expected, role_value in zip(ROLE_IDS, roles, strict=True):
        if not isinstance(role_value, dict) or set(role_value) != {
            "bytes_hex",
            "role",
            "sha256",
        }:
            _fail("role shape differs")
        if role_value["role"] != expected:
            _fail(f"expected role {expected!r}")
        encoded = role_value["bytes_hex"]
        declared_sha256 = role_value["sha256"]
        if (
            not isinstance(encoded, str)
            or LOWER_HEX.fullmatch(encoded) is None
            or not isinstance(declared_sha256, str)
            or LOWER_SHA256.fullmatch(declared_sha256) is None
        ):
            _fail("role representation differs")
        raw = bytes.fromhex(encoded)
        if hashlib.sha256(raw).hexdigest() != declared_sha256:
            _fail(f"role hash differs for {expected}")
        decoded[expected] = raw
        identities[expected] = declared_sha256
    return decoded, identities


def read_transfer_bundle(raw: bytes) -> tuple[SegmentEvidence, ...]:
    """Read exact two-replay transfer bytes and return first-replay evidence."""
    bundle = read_canonical_object(raw)
    if set(bundle) != {"profile_id", "promotable", "replays", "schema_id"}:
        _fail("bundle shape differs")
    if (
        bundle["profile_id"] != "AU-NSW-LH-SYN-SPS-v1"
        or bundle["promotable"] is not False
        or bundle["schema_id"] != "asw-0b5.certifier-input-bundle.v1"
    ):
        _fail("bundle authority differs")
    replays = bundle["replays"]
    if not isinstance(replays, list) or len(replays) != 2:
        _fail("exactly two replays are required")
    for ordinal, replay in enumerate(replays):
        if (
            not isinstance(replay, dict)
            or set(replay) != {"cases", "ordinal"}
            or replay["ordinal"] != ordinal
            or not isinstance(replay["cases"], list)
        ):
            _fail("replay shape or ordinal differs")
    if replays[0]["cases"] != replays[1]["cases"]:
        _fail("replay differs")
    result: list[SegmentEvidence] = []
    for case_value in replays[0]["cases"]:
        if (
            not isinstance(case_value, dict)
            or set(case_value) != {"case_id", "segments"}
            or not isinstance(case_value["case_id"], str)
            or not isinstance(case_value["segments"], list)
        ):
            _fail("case shape differs")
        for segment_value in case_value["segments"]:
            if (
                not isinstance(segment_value, dict)
                or set(segment_value) != {"roles", "segment_id"}
                or not isinstance(segment_value["segment_id"], str)
            ):
                _fail("segment shape differs")
            role_bytes, role_sha256 = _decoded_roles(segment_value)
            result.append(
                SegmentEvidence(
                    case_id=case_value["case_id"],
                    request=read_canonical_object(role_bytes["request"]),
                    role_bytes=role_bytes,
                    role_sha256=role_sha256,
                    segment_id=segment_value["segment_id"],
                    semantic=read_canonical_object(role_bytes["semantic-candidate"]),
                )
            )
    if not result:
        _fail("bundle has no segments")
    return tuple(result)


def _certifier_result_id(value: dict[str, Any]) -> str:
    payload = {key: child for key, child in value.items() if key != "result_content_id"}
    return hashlib.sha256(CERTIFIER_RESULT_DOMAIN + catalogue.canonical_json_bytes(payload)).hexdigest()


def read_certifier_result(
    raw: bytes,
    *,
    bundle_bytes: bytes,
    segments: tuple[SegmentEvidence, ...],
) -> CertifierEvidence:
    """Read one W3 result without importing or trusting the W3 result reader."""
    value = read_canonical_object(raw)
    if set(value) != {
        "authorities",
        "bundle_sha256",
        "cases",
        "checks",
        "first_failing_stage",
        "promotable",
        "residual_register",
        "result_content_id",
        "schema_id",
        "terminal_state",
    }:
        _fail("certifier result shape differs")
    declared_id = value["result_content_id"]
    if (
        not isinstance(declared_id, str)
        or LOWER_SHA256.fullmatch(declared_id) is None
        or declared_id != _certifier_result_id(value)
    ):
        _fail("certifier result identity differs")
    if value["bundle_sha256"] != hashlib.sha256(bundle_bytes).hexdigest():
        _fail("certifier result bundle identity differs")
    if value["authorities"] != {
        "profile_id": "AU-NSW-LH-SYN-SPS-v1",
        "protocol_id": "asw-0b4.independent-certification-protocol.v2",
        "w1_sha256": W1_PROTOCOL_SHA256,
        "w3_sha256": W3_PROTOCOL_SHA256,
    }:
        _fail("certifier authority differs")
    if (
        value["schema_id"] != "asw-0b5.certifier-result.v1"
        or value["promotable"] is not False
        or value["terminal_state"] != "quantitative-pending-w4"
        or value["first_failing_stage"] != "w4-tolerance-required"
    ):
        _fail("certifier result is not the W4 handoff state")
    checks = value["checks"]
    if (
        not isinstance(checks, list)
        or not checks
        or any(not isinstance(check, dict) or check.get("outcome") != "satisfied" for check in checks)
    ):
        _fail("certifier exact checks did not all pass")
    register = value["residual_register"]
    if not isinstance(register, list) or [item.get("check_id") for item in register] != [
        f"C-R{index:02d}" for index in range(1, 25)
    ]:
        _fail("certifier residual register differs")
    segment_results: dict[tuple[str, str], dict[str, Any]] = {}
    cases = value["cases"]
    if not isinstance(cases, list):
        _fail("certifier cases differ")
    for case_value in cases:
        if (
            not isinstance(case_value, dict)
            or set(case_value) != {"case_content_id", "case_id", "segments", "terminal_state"}
            or case_value["terminal_state"] != "quantitative-pending-w4"
            or not isinstance(case_value["case_id"], str)
            or not isinstance(case_value["segments"], list)
        ):
            _fail("certifier case shape differs")
        for segment_value in case_value["segments"]:
            if (
                not isinstance(segment_value, dict)
                or set(segment_value)
                != {
                    "capability",
                    "residuals",
                    "segment_id",
                    "terminal_state",
                }
                or segment_value["terminal_state"] != "quantitative-pending-w4"
                or not isinstance(segment_value["segment_id"], str)
            ):
                _fail("certifier segment shape differs")
            key = (case_value["case_id"], segment_value["segment_id"])
            if key in segment_results:
                _fail("duplicate certifier segment")
            segment_results[key] = segment_value
    transfer_inventory = [(item.case_id, item.segment_id) for item in segments]
    if list(segment_results) != transfer_inventory:
        _fail("certifier segment inventory differs")
    return CertifierEvidence(
        result_content_id=declared_id,
        segment_results=segment_results,
        terminal_state=value["terminal_state"],
        value=value,
    )
