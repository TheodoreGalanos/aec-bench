# ABOUTME: Serializes only permitted W3 candidate byte roles into a path-free certification envelope.
# ABOUTME: Excludes raw engine files, generator objects, workspace paths, pass assertions, and promotion claims.

from __future__ import annotations

import hashlib
from typing import Any, cast

from generator import request

BUNDLE_SCHEMA_ID = "asw-0b5.certifier-input-bundle.v1"
BUNDLE_DOMAIN = b"asw-0b5.certifier-input-bundle.v1\0"
ROLE_ORDER = (
    "request",
    "pump-a-original-curve",
    "pump-a-engine-curve",
    "pump-b-original-curve",
    "pump-b-engine-curve",
    "semantic-candidate",
)


class TransferError(ValueError):
    """Raised when generation results cannot form the exact W3 byte envelope."""


def _role(role: str, raw: bytes) -> dict[str, str]:
    return {
        "bytes_hex": raw.hex(),
        "role": role,
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def build_certifier_bundle(generation_result: dict[str, Any]) -> bytes:
    """Build the complete two-replay W3 input bundle from real W2 result bytes."""
    if generation_result.get("case_ids") != list(request.CASE_IDS):
        raise TransferError("generation case inventory differs")
    replays = generation_result.get("replays")
    if not isinstance(replays, list) or len(replays) != 2:
        raise TransferError("exactly two generation replays are required")
    serialized_replays: list[dict[str, Any]] = []
    for expected_ordinal, replay_value in enumerate(replays):
        if not isinstance(replay_value, dict) or replay_value.get("replay_index") != expected_ordinal:
            raise TransferError("generation replay order differs")
        cases = replay_value.get("cases")
        if not isinstance(cases, dict):
            raise TransferError("generation replay cases are absent")
        serialized_cases: list[dict[str, Any]] = []
        for case_id in request.CASE_IDS:
            case = cases.get(case_id)
            if not isinstance(case, dict) or case.get("case_id") != case_id:
                raise TransferError(f"generation result for {case_id} differs")
            request_bytes = case.get("request_bytes")
            segments = case.get("segments")
            if not isinstance(request_bytes, bytes) or not isinstance(segments, list):
                raise TransferError(f"permitted bytes for {case_id} are absent")
            serialized_segments: list[dict[str, Any]] = []
            for segment in segments:
                if not isinstance(segment, dict):
                    raise TransferError("generation segment shape differs")
                curve_bytes = segment.get("curve_bytes")
                semantic_bytes = segment.get("semantic_bytes")
                segment_id = segment.get("segment_id")
                if (
                    not isinstance(curve_bytes, dict)
                    or not isinstance(semantic_bytes, bytes)
                    or not isinstance(segment_id, str)
                ):
                    raise TransferError("generation segment permitted roles are absent")
                typed_curves = cast(dict[str, bytes], curve_bytes)
                roles = [
                    _role("request", request_bytes),
                    _role("pump-a-original-curve", typed_curves["pump-a-original"]),
                    _role("pump-a-engine-curve", typed_curves["pump-a-engine"]),
                    _role("pump-b-original-curve", typed_curves["pump-b-original"]),
                    _role("pump-b-engine-curve", typed_curves["pump-b-engine"]),
                    _role("semantic-candidate", semantic_bytes),
                ]
                if [role["role"] for role in roles] != list(ROLE_ORDER):
                    raise TransferError("certifier role order differs")
                serialized_segments.append(
                    {
                        "roles": roles,
                        "segment_id": segment_id,
                    }
                )
            serialized_cases.append(
                {
                    "case_id": case_id,
                    "segments": serialized_segments,
                }
            )
        serialized_replays.append(
            {
                "cases": serialized_cases,
                "ordinal": expected_ordinal,
            }
        )
    bundle = {
        "profile_id": request.PROFILE_ID,
        "promotable": False,
        "replays": serialized_replays,
        "schema_id": BUNDLE_SCHEMA_ID,
    }
    return request.canonical_json_bytes(bundle)


def bundle_sha256(raw: bytes) -> str:
    """Return the domain-separated W3 input-bundle identity."""
    return hashlib.sha256(BUNDLE_DOMAIN + raw).hexdigest()
