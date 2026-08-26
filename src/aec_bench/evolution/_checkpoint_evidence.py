# ABOUTME: Serializes exact trial, enrichment, and development evidence for AVO checkpoints.
# ABOUTME: Keeps evidence restoration separate from the public checkpoint state and storage contract.

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

from pydantic import Field, field_validator, model_validator

from aec_bench.contracts.artifacts import ArtifactRef
from aec_bench.contracts.behavioral_types import BondType, ClassifiedTrace, StructuralScore, TurnClassification
from aec_bench.contracts.evolution import (
    CandidateAssessment,
    EvolutionObservation,
    FieldScore,
    ObservationEnrichment,
    TraceDigest,
    WorkspaceSnapshot,
)
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.contracts.validators import NonEmptyStr, StrictModel
from aec_bench.evolution.core import EvaluatedCandidate
from aec_bench.evolution.development import DevelopmentEvaluationProvenance


class AVOCheckpointTurn(StrictModel):
    """Serializable form of one classified trace turn."""

    turn_index: int
    bond_type: BondType
    confidence: float
    rationale: str = ""


class AVOCheckpointTrace(StrictModel):
    """Serializable form of the optional classified trace enrichment."""

    trace_id: NonEmptyStr
    model_name: NonEmptyStr
    classifications: tuple[AVOCheckpointTurn, ...]
    metadata: dict[str, Any] = Field(default_factory=dict)


class AVOCheckpointStructuralScore(StrictModel):
    """Serializable form of the optional structural similarity enrichment."""

    trace_id: NonEmptyStr
    cosine_similarity: float
    edit_distance: int
    normalized_edit_distance: float
    reward: float | None = None


class AVOCheckpointEnrichment(StrictModel):
    """Exact JSON form of one observation's optional enrichment values."""

    classified_trace: AVOCheckpointTrace | None = None
    structural_score: AVOCheckpointStructuralScore | None = None
    field_scores: tuple[FieldScore, ...] = ()
    trace_digest: TraceDigest | None = None

    @classmethod
    def from_enrichment(cls, enrichment: ObservationEnrichment) -> AVOCheckpointEnrichment:
        """Convert current enrichment dataclasses to the persisted form."""

        if not isinstance(enrichment, ObservationEnrichment):
            raise TypeError("enrichment must be an ObservationEnrichment")
        classified_trace = None
        if enrichment.classified_trace is not None:
            trace = enrichment.classified_trace
            classified_trace = AVOCheckpointTrace(
                trace_id=trace.trace_id,
                model_name=trace.model_name,
                classifications=tuple(
                    AVOCheckpointTurn(
                        turn_index=item.turn_index,
                        bond_type=item.bond_type,
                        confidence=item.confidence,
                        rationale=item.rationale,
                    )
                    for item in trace.classifications
                ),
                metadata=dict(trace.metadata),
            )
        structural_score = None
        if enrichment.structural_score is not None:
            score = enrichment.structural_score
            structural_score = AVOCheckpointStructuralScore(
                trace_id=score.trace_id,
                cosine_similarity=score.cosine_similarity,
                edit_distance=score.edit_distance,
                normalized_edit_distance=score.normalized_edit_distance,
                reward=score.reward,
            )
        return cls(
            classified_trace=classified_trace,
            structural_score=structural_score,
            field_scores=tuple(enrichment.field_scores),
            trace_digest=enrichment.trace_digest,
        )

    def to_enrichment(self) -> ObservationEnrichment:
        """Restore the runtime enrichment value without losing trace detail."""

        trace = None
        if self.classified_trace is not None:
            trace = ClassifiedTrace(
                trace_id=self.classified_trace.trace_id,
                model_name=self.classified_trace.model_name,
                classifications=tuple(
                    TurnClassification(
                        turn_index=item.turn_index,
                        bond_type=item.bond_type,
                        confidence=item.confidence,
                        rationale=item.rationale,
                    )
                    for item in self.classified_trace.classifications
                ),
                metadata=dict(self.classified_trace.metadata),
            )
        score = None
        if self.structural_score is not None:
            score = StructuralScore(
                trace_id=self.structural_score.trace_id,
                cosine_similarity=self.structural_score.cosine_similarity,
                edit_distance=self.structural_score.edit_distance,
                normalized_edit_distance=self.structural_score.normalized_edit_distance,
                reward=self.structural_score.reward,
            )
        return ObservationEnrichment(
            classified_trace=trace,
            structural_score=score,
            field_scores=list(self.field_scores),
            trace_digest=self.trace_digest,
        )


class AVOCheckpointObservation(StrictModel):
    """One exact trial observation retained in a checkpoint."""

    trial: TrialRecord
    enrichment: AVOCheckpointEnrichment
    candidate_id: NonEmptyStr
    discipline: NonEmptyStr
    development_provenance: DevelopmentEvaluationProvenance
    extension_values: dict[str, Any] = Field(default_factory=dict)
    raw_output_path: str | None = None
    conversation_path: str | None = None
    trajectory_path: str | None = None

    @classmethod
    def from_observation(cls, observation: EvolutionObservation) -> AVOCheckpointObservation:
        """Convert one runtime observation to its exact persisted form."""

        if not isinstance(observation, EvolutionObservation):
            raise TypeError("observation must be an EvolutionObservation")
        provenance = observation.trial.pending_extensions.get("development_evaluation")
        if not isinstance(provenance, DevelopmentEvaluationProvenance):
            raise ValueError("checkpoint observation requires DevelopmentEvaluationProvenance")
        extension_values = {
            kind: _json_extension_value(value)
            for kind, value in observation.trial.pending_extensions.items()
            if kind != "development_evaluation"
        }
        return cls(
            trial=observation.trial,
            enrichment=AVOCheckpointEnrichment.from_enrichment(observation.enrichment),
            candidate_id=observation.candidate_id,
            discipline=observation.discipline,
            development_provenance=provenance,
            extension_values=extension_values,
            raw_output_path=(
                observation.trial.output.raw_output_path if observation.trial.output is not None else None
            ),
            conversation_path=(
                observation.trial.output.conversation_path if observation.trial.output is not None else None
            ),
            trajectory_path=(
                observation.trial.output.trajectory_path if observation.trial.output is not None else None
            ),
        )

    def to_observation(self) -> EvolutionObservation:
        """Restore one runtime observation from validated checkpoint material."""

        restored = self.trial.model_copy(deep=True)
        existing_provenance = restored.pending_extensions.get("development_evaluation")
        if existing_provenance is None:
            restored.attach_extension("development_evaluation", self.development_provenance)
        elif existing_provenance != self.development_provenance:
            raise ValueError("checkpoint development provenance conflicts with TrialRecord extension")
        for kind, value in self.extension_values.items():
            if kind not in restored.pending_extensions:
                restored.attach_extension(kind, value)
            elif restored.pending_extensions[kind] != value:
                raise ValueError(f"checkpoint extension value conflicts with TrialRecord extension: {kind}")
        if restored.output is not None:
            restored.output.bind_runtime_paths(
                raw_output_path=self.raw_output_path,
                conversation_path=self.conversation_path,
                trajectory_path=self.trajectory_path,
            )
        return EvolutionObservation(
            trial=restored,
            enrichment=self.enrichment.to_enrichment(),
            candidate_id=self.candidate_id,
            discipline=self.discipline,
        )


class AVOCheckpointEvaluatedCandidate(StrictModel):
    """Exact candidate snapshot and ordered evidence from one evaluation."""

    snapshot: WorkspaceSnapshot
    observations: tuple[AVOCheckpointObservation, ...]
    assessment: CandidateAssessment

    @model_validator(mode="after")
    def validate_snapshot_and_evidence(self) -> AVOCheckpointEvaluatedCandidate:
        if not self.observations:
            raise ValueError("checkpoint evaluated candidate evidence must not be empty")
        # Reuse the runtime invariant so persisted bytes cannot create a weaker
        # candidate/evidence relationship than an in-memory evaluation.
        EvaluatedCandidate(
            snapshot=self.snapshot,
            observations=tuple(item.to_observation() for item in self.observations),
            assessment=self.assessment,
        )
        return self

    @classmethod
    def from_evaluated_candidate(cls, candidate: EvaluatedCandidate) -> AVOCheckpointEvaluatedCandidate:
        """Convert one runtime candidate and all of its ordered evidence."""

        if not isinstance(candidate, EvaluatedCandidate):
            raise TypeError("candidate must be an EvaluatedCandidate")
        return cls(
            snapshot=candidate.snapshot,
            observations=tuple(AVOCheckpointObservation.from_observation(item) for item in candidate.observations),
            assessment=candidate.assessment,
        )

    def to_evaluated_candidate(self) -> EvaluatedCandidate:
        """Restore one runtime candidate from validated checkpoint material."""

        return EvaluatedCandidate(
            snapshot=self.snapshot,
            observations=tuple(item.to_observation() for item in self.observations),
            assessment=self.assessment,
        )


def _trial_artifact_refs(trial: TrialRecord) -> tuple[ArtifactRef, ...]:
    """Return every exact artifact reference carried by one trial record."""

    return tuple(
        (
            *(item.artifact for item in trial.extension_refs),
            *(item.artifact for item in trial.authority_evidence),
            *(item.artifact for item in trial.input.input_files or ()),
            *((item.artifact for item in trial.output.artifacts) if trial.output is not None else ()),
            *((trial.provider_evidence,) if trial.provider_evidence is not None else ()),
        )
    )


def _json_extension_value(value: Any) -> Any:
    """Convert one extension value to a JSON-compatible persisted value."""

    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    return value


class AVOCheckpointEvidenceRef(StrictModel):
    """Exact identity of one development evidence item and its artifacts."""

    attempt_id: NonEmptyStr | None = None
    run_id: NonEmptyStr
    experiment_id: NonEmptyStr
    candidate_id: NonEmptyStr
    trial_id: NonEmptyStr
    evaluation_case_id: NonEmptyStr
    revision: int
    artifact_refs: tuple[ArtifactRef, ...] = ()

    @field_validator("revision")
    @classmethod
    def validate_revision(cls, value: int) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError("checkpoint evidence revision must be a non-negative integer")
        return value


def _candidate_evidence_refs(
    candidate: AVOCheckpointEvaluatedCandidate,
    *,
    revision: int,
    attempt_id: str | None,
) -> tuple[AVOCheckpointEvidenceRef, ...]:
    """Project exact persisted evidence identities from one candidate record."""

    return tuple(
        AVOCheckpointEvidenceRef(
            attempt_id=attempt_id,
            run_id=observation.trial.run_id,
            experiment_id=observation.development_provenance.experiment_id,
            candidate_id=observation.candidate_id,
            trial_id=observation.trial.trial_id,
            evaluation_case_id=case_id,
            revision=revision,
            artifact_refs=_trial_artifact_refs(observation.trial),
        )
        for case_id, observation in zip(
            candidate.assessment.evaluation_case_ids,
            candidate.observations,
            strict=True,
        )
    )


__all__ = (
    "AVOCheckpointEnrichment",
    "AVOCheckpointEvidenceRef",
    "AVOCheckpointEvaluatedCandidate",
    "AVOCheckpointObservation",
    "AVOCheckpointStructuralScore",
    "AVOCheckpointTrace",
    "AVOCheckpointTurn",
    "_candidate_evidence_refs",
)
