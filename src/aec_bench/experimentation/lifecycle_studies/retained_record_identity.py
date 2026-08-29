# ABOUTME: Compares finalized lifecycle study records with their pending retained artifact sources.
# ABOUTME: Keeps one semantic and artifact identity policy for current and historical study records.

from __future__ import annotations

import hashlib
from typing import Any, cast

from aec_bench.contracts.trial_record import EvidenceStatus, TrialRecord


def matches_retained_lifecycle_record(
    record: TrialRecord,
    expected: TrialRecord,
    *,
    allow_omitted_visibility: bool = False,
) -> bool:
    """Compare record semantics and retained bytes, with one explicit historical exception."""
    if record.run_manifest != expected.run_manifest or record.evidence_status is not EvidenceStatus.VERIFIED:
        return False
    record_payload = _trial_semantic_payload(record)
    expected_payload = _trial_semantic_payload(expected)
    if (
        allow_omitted_visibility
        and record.input.visibility is None
        and "visibility" not in record.input.model_fields_set
    ):
        cast(dict[str, Any], expected_payload["input"])["visibility"] = None
    if record_payload != expected_payload:
        return False
    if (
        record.adaptation != expected.adaptation
        or record.lifecycle_execution != expected.lifecycle_execution
        or record.lifecycle_provenance != expected.lifecycle_provenance
    ):
        return False
    return _retained_artifact_identity(record) == _pending_artifact_identity(expected)


def _trial_semantic_payload(record: TrialRecord) -> dict[str, Any]:
    payload = record.model_dump(mode="json")
    payload.pop("evidence_status", None)
    payload.pop("authority_evidence", None)
    payload.pop("extension_refs", None)
    cast(dict[str, Any], payload["input"]).pop("input_files", None)
    output = cast(dict[str, Any] | None, payload.get("output"))
    if output is not None:
        for field in ("raw_output", "conversation", "trajectory", "artifacts"):
            output.pop(field, None)
    return payload


def _retained_artifact_identity(record: TrialRecord) -> tuple[tuple[object, ...], ...]:
    identities: list[tuple[object, ...]] = [
        (
            "output",
            item.role,
            item.logical_path,
            item.artifact.sha256,
            item.artifact.size_bytes,
            item.artifact.media_type,
        )
        for item in record.outputs.artifacts
    ]
    identities.extend(
        (
            "authority",
            item.authority_kind.value,
            item.protocol,
            item.artifact.sha256,
            item.artifact.size_bytes,
            item.artifact.media_type,
        )
        for item in record.authority_evidence
    )
    identities.extend(
        ("input", item.source, item.artifact.sha256, item.artifact.size_bytes, item.artifact.media_type)
        for item in record.input.input_files or ()
    )
    return tuple(sorted(identities, key=repr))


def _pending_artifact_identity(record: TrialRecord) -> tuple[tuple[object, ...], ...]:
    identities: list[tuple[object, ...]] = []
    for role, (path, media_type, logical_path) in record.pending_artifacts.items():
        payload = path.read_bytes()
        semantic_role = role.removeprefix("output:")
        if role.startswith("output:"):
            semantic_role = semantic_role.rpartition(":")[0] or semantic_role
        if not payload and semantic_role in {"conversation", "trajectory"}:
            continue
        digest = hashlib.sha256(payload).hexdigest()
        size = len(payload)
        if role.startswith("authority:"):
            _, authority_kind, protocol = role.split(":", 2)
            identities.append(("authority", authority_kind, protocol, digest, size, media_type))
        elif role.startswith("input:"):
            source = role.removeprefix("input:").partition(":")[0]
            identities.append(("input", source or None, digest, size, media_type))
        else:
            identities.append(("output", semantic_role, logical_path, digest, size, media_type))
    return tuple(sorted(identities, key=repr))
