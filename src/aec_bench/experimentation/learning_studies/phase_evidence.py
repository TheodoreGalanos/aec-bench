"""Group lifecycle phase-evidence extension artefacts by opaque phase ID."""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass

from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.ledger.artifact_repository import ArtifactRepository

PHASE_EVIDENCE_KIND = "lifecycle_learning_evidence"


@dataclass(frozen=True)
class PhaseEvidenceEntry:
    trial_id: str
    phase_id: str
    raw_bytes: bytes


def group_phase_evidence(
    records: Iterable[TrialRecord],
    *,
    artifact_repository: ArtifactRepository,
) -> dict[str, list[PhaseEvidenceEntry]]:
    """Group extension phase records without interpreting their payloads."""

    groups: dict[str, list[PhaseEvidenceEntry]] = {}
    for record in records:
        for extension in record.extension_refs:
            if extension.extension_kind != PHASE_EVIDENCE_KIND:
                continue
            try:
                payload = json.loads(artifact_repository.read_bytes(extension.artifact))
            except (OSError, RuntimeError, ValueError, TypeError):
                continue
            if not isinstance(payload, dict) or not isinstance(payload.get("phase_records"), list):
                continue
            for phase in payload["phase_records"]:
                if not isinstance(phase, dict):
                    continue
                phase_id = phase.get("phase_id")
                if not isinstance(phase_id, str) or not phase_id:
                    continue
                raw_phase = json.dumps(
                    phase,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                ).encode("utf-8")
                groups.setdefault(phase_id, []).append(
                    PhaseEvidenceEntry(
                        trial_id=record.trial_id,
                        phase_id=phase_id,
                        raw_bytes=raw_phase,
                    )
                )
    return groups


__all__ = ("PHASE_EVIDENCE_KIND", "PhaseEvidenceEntry", "group_phase_evidence")
