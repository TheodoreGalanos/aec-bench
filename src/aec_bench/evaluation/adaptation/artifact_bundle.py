# ABOUTME: Persistable adaptation artefact bundles compiled from accepted trial outputs.
# ABOUTME: Filters preserved bands while retaining family-scoped acceptance summaries.

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.evaluation.adaptation.acceptance import (
    AcceptanceThresholds,
    classify_adaptation_trial,
    summarize_acceptance_bands,
)


@dataclass(frozen=True)
class AdaptationArtifactBundle:
    family_id: str
    seed_task_id: str
    source_trial_count: int
    preserved_trial_count: int
    band_counts: dict[str, int]
    artefacts: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "family_id": self.family_id,
            "seed_task_id": self.seed_task_id,
            "source_trial_count": self.source_trial_count,
            "preserved_trial_count": self.preserved_trial_count,
            "band_counts": self.band_counts,
            "artefacts": self.artefacts,
        }


def build_adaptation_artifact_bundle(
    records: list[TrialRecord],
    *,
    thresholds: AcceptanceThresholds | None = None,
) -> AdaptationArtifactBundle:
    adaptation_records = [record for record in records if record.adaptation is not None]
    if not adaptation_records:
        raise ValueError("adaptation bundle requires at least one adaptation record")

    family_ids = {record.adaptation.family_id for record in adaptation_records if record.adaptation}
    if len(family_ids) != 1:
        raise ValueError("adaptation bundle records must belong to the same adaptation family")

    seed_task_ids = {record.adaptation.seed_task_id for record in adaptation_records if record.adaptation}
    if len(seed_task_ids) != 1:
        raise ValueError("adaptation bundle records must share the same seed task")

    summary = summarize_acceptance_bands(adaptation_records, thresholds=thresholds)
    artefacts: list[dict[str, Any]] = []
    for record in adaptation_records:
        decision = classify_adaptation_trial(record, thresholds=thresholds)
        if not decision.preserve:
            continue
        adaptation = record.adaptation
        if adaptation is None:
            continue
        artefacts.append(
            {
                "trial_id": record.trial_id,
                "task_id": record.task.task_id,
                "variation_key": adaptation.variation_key,
                "variation": dict(adaptation.variation),
                "acceptance_band": decision.band.value,
                "reward": record.evaluation.reward,
                "completeness": record.completeness.value,
                "raw_output_path": record.outputs.raw_output_path,
                "conversation_path": record.outputs.conversation_path,
                "output_path": (
                    record.outputs.agent_output.output_path if record.outputs.agent_output is not None else None
                ),
            }
        )

    return AdaptationArtifactBundle(
        family_id=family_ids.pop(),
        seed_task_id=seed_task_ids.pop(),
        source_trial_count=len(adaptation_records),
        preserved_trial_count=len(artefacts),
        band_counts=summary.band_counts,
        artefacts=artefacts,
    )


def export_adaptation_artifact_bundle_json(
    bundle: AdaptationArtifactBundle,
    output_path: Path,
) -> Path:
    output_path.write_text(json.dumps(bundle.to_dict(), indent=2), encoding="utf-8")
    return output_path
