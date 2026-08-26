# ABOUTME: Defines the durable, validated state document for one AVO call.
# ABOUTME: Persists exact workspace and development evidence through the ledger durability boundary.

from __future__ import annotations

import json
import math
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator

from aec_bench.contracts.evolution import (
    MutationSummary,
    SelectionRecord,
    VariationUsage,
    WorkspaceSnapshot,
)
from aec_bench.contracts.trial_record import RunManifest
from aec_bench.contracts.validators import NonEmptyStr, StrictModel
from aec_bench.evolution._checkpoint_evidence import (
    AVOCheckpointEnrichment,
    AVOCheckpointEvaluatedCandidate,
    AVOCheckpointEvidenceRef,
    AVOCheckpointObservation,
    AVOCheckpointStructuralScore,
    AVOCheckpointTrace,
    AVOCheckpointTurn,
    _candidate_evidence_refs,
)
from aec_bench.evolution.cancellation import AVOCancellationCode
from aec_bench.evolution.core import (
    AVOBudget,
    AVOState,
    DevelopmentAttempt,
    EvaluatedCandidate,
    VariationResult,
    VariationStatus,
)
from aec_bench.evolution.memory import AVO_MEMORY_LIMIT, AVOMemoryEntry, validate_memory_entries
from aec_bench.evolution.supervision import AVOSupervisionRecord
from aec_bench.ledger.durability import mkdir_durable, replace_file_bytes_durable

AVO_CHECKPOINT_SCHEMA_VERSION: Literal[1] = 1
"""The only persisted checkpoint schema currently accepted by the reader."""

AVOExternalEffectOperation = Literal["model_request", "development_evaluation", "compaction", "supervisor_request"]
"""External operations that require durable incomplete-effect reconciliation."""


class AVOCheckpointCompatibilityError(ValueError):
    """Raised when checkpoint bytes do not use the current schema."""


class AVOIncompleteExternalEffectError(RuntimeError):
    """Raised when a checkpoint contains an effect that needs reconciliation."""

    def __init__(self, effect: AVOIncompleteExternalEffect | None = None, cause: BaseException | None = None) -> None:
        self.effect = effect
        self.cause = cause
        if effect is None:
            message = "AVO checkpoint contains an incomplete external effect that requires reconciliation."
        else:
            message = (
                f"AVO external effect {effect.effect_id!r} ({effect.operation}) is incomplete and "
                "must be reconciled before resume."
            )
        if cause is not None:
            message = f"{message} Cause: {cause}"
        super().__init__(message)


def _same_workspace_material(left: WorkspaceSnapshot, right: WorkspaceSnapshot) -> bool:
    """Compare the material that can be resumed or submitted."""

    return left.system_prompt == right.system_prompt and left.skills == right.skills


class AVOCheckpointAttempt(StrictModel):
    """Exact development attempt material, including its evaluation evidence."""

    attempt_id: NonEmptyStr
    revision: int
    evaluated: AVOCheckpointEvaluatedCandidate
    mutation: MutationSummary
    hypothesis: NonEmptyStr
    usage_after: AVOUsageSnapshot

    @field_validator("revision")
    @classmethod
    def validate_revision(cls, value: int) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError("checkpoint attempt revision must be a non-negative integer")
        return value

    @model_validator(mode="after")
    def validate_runtime_attempt(self) -> AVOCheckpointAttempt:
        DevelopmentAttempt(
            attempt_id=self.attempt_id,
            revision=self.revision,
            evaluated=self.evaluated.to_evaluated_candidate(),
            mutation=self.mutation,
            hypothesis=self.hypothesis,
            usage_after=self.usage_after.to_usage(),
        )
        return self

    @classmethod
    def from_attempt(cls, attempt: DevelopmentAttempt) -> AVOCheckpointAttempt:
        """Convert one runtime development attempt."""

        if not isinstance(attempt, DevelopmentAttempt):
            raise TypeError("attempt must be a DevelopmentAttempt")
        return cls(
            attempt_id=attempt.attempt_id,
            revision=attempt.revision,
            evaluated=AVOCheckpointEvaluatedCandidate.from_evaluated_candidate(attempt.evaluated),
            mutation=attempt.mutation,
            hypothesis=attempt.hypothesis,
            usage_after=AVOUsageSnapshot.from_usage(attempt.usage_after),
        )

    def to_attempt(self) -> DevelopmentAttempt:
        """Restore one runtime development attempt."""

        return DevelopmentAttempt(
            attempt_id=self.attempt_id,
            revision=self.revision,
            evaluated=self.evaluated.to_evaluated_candidate(),
            mutation=self.mutation,
            hypothesis=self.hypothesis,
            usage_after=self.usage_after.to_usage(),
        )


class AVOUsageSnapshot(StrictModel):
    """Persisted exact usage counters and cost-plane knowledge."""

    model_requests: int = 0
    tool_calls: int = 0
    development_evaluations: int = 0
    supervisor_interventions: int = 0
    input_tokens: int | None = None
    output_tokens: int | None = None
    model_cost_usd: float | None = None
    development_evaluation_cost_usd: float | None = None
    elapsed_seconds: float = 0.0

    @field_validator(
        "model_requests",
        "tool_calls",
        "development_evaluations",
        "supervisor_interventions",
    )
    @classmethod
    def validate_counters(cls, value: int) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError("checkpoint usage counters must be non-negative integers")
        return value

    @field_validator("model_cost_usd", "development_evaluation_cost_usd", "elapsed_seconds")
    @classmethod
    def validate_numbers(cls, value: float | None) -> float | None:
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value) or value < 0:
            raise ValueError("checkpoint usage values must be finite and non-negative")
        return value

    @field_validator("input_tokens", "output_tokens")
    @classmethod
    def validate_token_counts(cls, value: int | None) -> int | None:
        if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
            raise ValueError("checkpoint token counts must be non-negative integers")
        return value

    @classmethod
    def from_usage(cls, usage: VariationUsage) -> AVOUsageSnapshot:
        """Convert exact runtime usage, retaining unknown costs as ``None``."""

        if not isinstance(usage, VariationUsage):
            raise TypeError("usage must be a VariationUsage")
        return cls(**asdict(usage))

    def to_usage(self) -> VariationUsage:
        """Restore exact runtime usage."""

        return VariationUsage(**self.model_dump())


class AVOBudgetSnapshot(StrictModel):
    """Persisted budget limits used by one AVO call."""

    max_model_requests: int = 12
    max_tool_calls: int = 40
    max_development_evaluations: int = 7
    max_input_tokens: int | None = None
    max_output_tokens: int | None = None
    max_elapsed_seconds: float = 1800.0
    max_consecutive_evaluation_errors: int = 2
    max_stagnant_evaluations: int = 3
    max_supervisor_interventions: int = 0
    max_cost_usd: float | None = None

    @field_validator(
        "max_model_requests",
        "max_tool_calls",
        "max_development_evaluations",
        "max_consecutive_evaluation_errors",
        "max_stagnant_evaluations",
    )
    @classmethod
    def validate_positive_limits(cls, value: int) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError("checkpoint active budget limits must be positive integers")
        return value

    @field_validator("max_supervisor_interventions")
    @classmethod
    def validate_supervisor_limit(cls, value: int) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError("checkpoint supervisor budget must be a non-negative integer")
        return value

    @field_validator("max_elapsed_seconds", "max_cost_usd")
    @classmethod
    def validate_positive_numbers(cls, value: float | None) -> float | None:
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value) or value <= 0:
            raise ValueError("checkpoint active budget values must be finite and positive")
        return value

    @field_validator("max_input_tokens", "max_output_tokens")
    @classmethod
    def validate_token_limits(cls, value: int | None) -> int | None:
        if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value <= 0):
            raise ValueError("checkpoint token limits must be positive integers")
        return value

    @classmethod
    def from_budget(cls, budget: AVOBudget) -> AVOBudgetSnapshot:
        """Convert one runtime budget."""

        if not isinstance(budget, AVOBudget):
            raise TypeError("budget must be an AVOBudget")
        return cls(**asdict(budget))

    def to_budget(self) -> AVOBudget:
        """Restore one runtime budget."""

        return AVOBudget(**self.model_dump())


class AVOConfigurationIdentity(StrictModel):
    """Explicit behavior-affecting identity required for checkpoint compatibility."""

    model_identity: NonEmptyStr
    supervisor_model_identity: NonEmptyStr
    tool_identity: NonEmptyStr
    development_evaluator_identity: NonEmptyStr
    configuration_identity: NonEmptyStr


class AVOIncompleteExternalEffect(StrictModel):
    """An external operation whose completion is not yet confirmed."""

    effect_id: NonEmptyStr
    operation: AVOExternalEffectOperation
    reason: NonEmptyStr
    status: Literal["incomplete"] = "incomplete"
    observed_at: datetime | None = None

    @field_validator("observed_at")
    @classmethod
    def validate_observed_at(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("checkpoint incomplete effect timestamps must include a timezone")
        return value


class AVOCheckpointTerminalResult(StrictModel):
    """Terminal result retained with a checkpoint for idempotent later restore."""

    status: VariationStatus
    reasoning: NonEmptyStr
    usage: AVOUsageSnapshot
    child: WorkspaceSnapshot | None = None
    mutation: MutationSummary | None = None
    attempt_id: NonEmptyStr | None = None
    cancellation_code: AVOCancellationCode | None = None

    @model_validator(mode="after")
    def validate_terminal_shape(self) -> AVOCheckpointTerminalResult:
        if self.status is VariationStatus.SUBMITTED:
            if self.child is None or self.mutation is None or self.attempt_id is None:
                raise ValueError("submitted checkpoint result requires child, mutation, and attempt_id")
        elif self.child is not None or self.mutation is not None or self.attempt_id is not None:
            raise ValueError(f"{self.status.value} checkpoint result must not contain child, mutation, or attempt")
        if self.status is VariationStatus.CANCELLED and self.cancellation_code is None:
            raise ValueError("cancelled checkpoint result requires a cancellation_code")
        if self.status is not VariationStatus.CANCELLED and self.cancellation_code is not None:
            raise ValueError("cancellation_code is only valid for a cancelled checkpoint result")
        return self

    @classmethod
    def from_result(
        cls,
        result: VariationResult,
        *,
        cancellation_code: AVOCancellationCode | None = None,
    ) -> AVOCheckpointTerminalResult:
        """Convert one terminal runtime result."""

        if not isinstance(result, VariationResult):
            raise TypeError("result must be a VariationResult")
        return cls(
            status=result.status,
            reasoning=result.reasoning,
            usage=AVOUsageSnapshot.from_usage(result.usage),
            child=result.child,
            mutation=result.mutation,
            attempt_id=result.attempt.attempt_id if result.attempt is not None else None,
            cancellation_code=cancellation_code,
        )


class AVOCheckpoint(StrictModel):
    """The sole validated resume authority for one durable AVO call."""

    schema_version: Literal[1] = AVO_CHECKPOINT_SCHEMA_VERSION
    run_id: NonEmptyStr
    variation_id: NonEmptyStr
    parent_candidate_id: NonEmptyStr
    final_child_candidate_id: NonEmptyStr
    selection: SelectionRecord
    development_case_ids: tuple[NonEmptyStr, ...]
    development_evidence_refs: tuple[AVOCheckpointEvidenceRef, ...] = ()
    configuration_identity: AVOConfigurationIdentity
    parent_snapshot: WorkspaceSnapshot
    parent_evidence: AVOCheckpointEvaluatedCandidate | None = None
    current_revision: int
    current_snapshot: WorkspaceSnapshot
    run_manifests: dict[str, RunManifest] = Field(default_factory=dict)
    evaluated_attempts: tuple[AVOCheckpointAttempt, ...] = ()
    best_attempt_id: NonEmptyStr | None = None
    consecutive_without_progress: int = 0
    consecutive_evaluation_errors: int = 0
    exhausted_direction_requested: bool = False
    budget: AVOBudgetSnapshot
    usage: AVOUsageSnapshot
    structured_memory: tuple[AVOMemoryEntry, ...] = ()
    supervision_records: tuple[AVOSupervisionRecord, ...] = ()
    incomplete_external_effects: tuple[AVOIncompleteExternalEffect, ...] = ()
    terminal_result: AVOCheckpointTerminalResult | None = None

    @field_validator("current_revision", "consecutive_without_progress", "consecutive_evaluation_errors")
    @classmethod
    def validate_counters(cls, value: int) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError("checkpoint state counters must be non-negative integers")
        return value

    @field_validator("exhausted_direction_requested")
    @classmethod
    def validate_direction_request(cls, value: bool) -> bool:
        if not isinstance(value, bool):
            raise TypeError("checkpoint exhausted_direction_requested must be a boolean")
        return value

    @field_validator("development_case_ids")
    @classmethod
    def validate_case_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            raise ValueError("checkpoint development_case_ids must not be empty")
        if len(value) != len(set(value)):
            raise ValueError("checkpoint development_case_ids must be unique")
        return value

    @field_validator("structured_memory")
    @classmethod
    def validate_memory_limit(cls, value: tuple[AVOMemoryEntry, ...]) -> tuple[AVOMemoryEntry, ...]:
        validate_memory_entries(value)
        if len(value) > AVO_MEMORY_LIMIT:
            raise ValueError(f"checkpoint structured_memory must contain at most {AVO_MEMORY_LIMIT} entries")
        return value

    @field_validator("incomplete_external_effects")
    @classmethod
    def validate_incomplete_effect_ids(
        cls,
        value: tuple[AVOIncompleteExternalEffect, ...],
    ) -> tuple[AVOIncompleteExternalEffect, ...]:
        effect_ids = tuple(item.effect_id for item in value)
        if len(effect_ids) != len(set(effect_ids)):
            raise ValueError("checkpoint incomplete external effect IDs must be unique")
        return value

    @model_validator(mode="after")
    def validate_consistency(self) -> AVOCheckpoint:
        if self.selection.parent_candidate_id != self.parent_candidate_id:
            raise ValueError("checkpoint selection parent must match parent_candidate_id")
        if self.parent_candidate_id == self.final_child_candidate_id:
            raise ValueError("checkpoint parent and final child candidate IDs must differ")
        if self.parent_snapshot.candidate_id != self.parent_candidate_id:
            raise ValueError("checkpoint parent_snapshot must match parent_candidate_id")
        if self.current_snapshot.candidate_id != self.final_child_candidate_id:
            raise ValueError("checkpoint current_snapshot must match final_child_candidate_id")
        if self.terminal_result is not None and self.incomplete_external_effects:
            raise ValueError("terminal checkpoint must not retain incomplete external effects")
        in_flight_supervisions = tuple(
            effect for effect in self.incomplete_external_effects if effect.operation == "supervisor_request"
        )
        if len(in_flight_supervisions) > 1:
            raise ValueError("checkpoint may contain at most one incomplete supervisor request")
        if len(self.supervision_records) > self.budget.max_supervisor_interventions:
            raise ValueError("checkpoint supervision_records exceed the configured supervisor intervention budget")
        if len(self.supervision_records) + len(in_flight_supervisions) != self.usage.supervisor_interventions:
            raise ValueError("checkpoint supervision_records and incomplete requests must match supervisor usage")
        if self.terminal_result is not None and self.exhausted_direction_requested:
            raise ValueError("terminal checkpoint cannot retain a pending exhausted-direction request")

        # Parent development evidence is absent only before the first baseline
        # evaluation. This shape is needed to durably represent cancellation or
        # an interrupted evaluator call without substituting host evidence.
        if self.parent_evidence is None:
            pre_baseline = (
                self.current_revision == 0
                and not self.evaluated_attempts
                and self.best_attempt_id is None
                and not self.development_evidence_refs
                and not self.run_manifests
            )
            if not pre_baseline:
                raise ValueError("checkpoint without parent evidence must be pre-baseline with no evidence")
            if not _same_workspace_material(self.parent_snapshot, self.current_snapshot):
                raise ValueError("checkpoint without parent evidence must retain exact parent material")
            if (
                self.usage.model_requests != 0
                or self.usage.tool_calls != 0
                or self.usage.development_evaluations != 0
                or self.usage.supervisor_interventions != 0
                or self.usage.model_cost_usd is not None
                or self.usage.development_evaluation_cost_usd is not None
            ):
                raise ValueError(
                    "checkpoint without parent evidence must have zero usage counters and no recorded costs"
                )
            if self.terminal_result is None:
                if not (
                    len(self.incomplete_external_effects) == 1
                    and self.incomplete_external_effects[0].operation == "development_evaluation"
                    and self.incomplete_external_effects[0].effect_id.endswith(":development-parent")
                ):
                    raise ValueError(
                        "checkpoint without parent evidence must have the parent development incomplete marker"
                    )
            elif self.terminal_result.status is VariationStatus.BUDGET_EXHAUSTED:
                if self.usage.elapsed_seconds < self.budget.max_elapsed_seconds:
                    raise ValueError(
                        "pre-baseline budget exhaustion requires elapsed_seconds to reach max_elapsed_seconds"
                    )
            elif self.terminal_result.status not in (VariationStatus.CANCELLED, VariationStatus.ABSTAINED):
                raise ValueError(
                    "checkpoint without parent evidence may only be terminal cancellation, abstention, "
                    "or budget exhaustion"
                )
        elif self.parent_evidence.snapshot.candidate_id != self.parent_candidate_id:
            raise ValueError("checkpoint parent_evidence must match parent_candidate_id")
        elif self.parent_evidence.assessment.evaluation_case_ids != self.development_case_ids:
            raise ValueError("checkpoint parent evidence cases must match development_case_ids exactly")

        evidence_candidates = () if self.parent_evidence is None else (self.parent_evidence,)

        expected_run_ids = {
            observation.trial.run_id
            for candidate in (
                *evidence_candidates,
                *(item.evaluated for item in self.evaluated_attempts),
            )
            for observation in candidate.observations
        }
        if set(self.run_manifests) != expected_run_ids:
            raise ValueError("checkpoint run_manifests must cover every evidence run_id exactly")
        for run_id, manifest in self.run_manifests.items():
            if run_id != manifest.run_id:
                raise ValueError("checkpoint run_manifests keys must match manifest run_id")
        for candidate, revision in (
            *((candidate, 0) for candidate in evidence_candidates),
            *((item.evaluated, item.revision) for item in self.evaluated_attempts),
        ):
            for observation in candidate.observations:
                manifest = self.run_manifests[observation.trial.run_id]
                observation.trial.bind_run_manifest(manifest)
                provenance = observation.development_provenance
                if provenance.experiment_id != manifest.experiment_id:
                    raise ValueError("checkpoint development provenance experiment_id must match RunManifest")
                if provenance.trial_id != observation.trial.trial_id:
                    raise ValueError("checkpoint development provenance trial_id must match TrialRecord")
                if provenance.candidate_id != observation.candidate_id:
                    raise ValueError("checkpoint development provenance candidate_id must match observation")
                if provenance.revision != revision:
                    raise ValueError("checkpoint development provenance revision must match evidence revision")

        current_attempt = next(
            (item for item in self.evaluated_attempts if item.revision == self.current_revision),
            None,
        )
        if current_attempt is not None:
            if (
                current_attempt.evaluated.snapshot.system_prompt != self.current_snapshot.system_prompt
                or current_attempt.evaluated.snapshot.skills != self.current_snapshot.skills
            ):
                raise ValueError("checkpoint current_snapshot must match exact current evaluated attempt material")

        attempt_ids = tuple(item.attempt_id for item in self.evaluated_attempts)
        revisions = tuple(item.revision for item in self.evaluated_attempts)
        snapshot_ids = tuple(item.evaluated.snapshot.candidate_id for item in self.evaluated_attempts)
        trial_ids = tuple(
            observation.trial.trial_id
            for item in self.evaluated_attempts
            for observation in item.evaluated.observations
        )
        if len(attempt_ids) != len(set(attempt_ids)):
            raise ValueError("checkpoint attempt IDs must be unique")
        if len(revisions) != len(set(revisions)):
            raise ValueError("checkpoint attempt revisions must be unique")
        if len(snapshot_ids) != len(set(snapshot_ids)):
            raise ValueError("checkpoint attempt snapshot IDs must be unique")
        if len(trial_ids) != len(set(trial_ids)):
            raise ValueError("checkpoint attempt trial IDs must be unique")
        all_trial_ids = tuple(
            observation.trial.trial_id
            for candidate in (
                *evidence_candidates,
                *(item.evaluated for item in self.evaluated_attempts),
            )
            for observation in candidate.observations
        )
        if len(all_trial_ids) != len(set(all_trial_ids)):
            raise ValueError("checkpoint evidence trial IDs must be unique across parent and attempts")
        if self.best_attempt_id is not None and self.best_attempt_id not in attempt_ids:
            raise ValueError("checkpoint best_attempt_id must reference an attempt")
        validate_memory_entries(self.structured_memory)
        for attempt in self.evaluated_attempts:
            if attempt.evaluated.assessment.evaluation_case_ids != self.development_case_ids:
                raise ValueError("checkpoint attempt evaluation cases must match development_case_ids exactly")
        expected_evidence_refs = (
            ()
            if self.parent_evidence is None
            else _candidate_evidence_refs(self.parent_evidence, revision=0, attempt_id=None)
        )
        expected_evidence_refs += tuple(
            evidence_ref
            for attempt in self.evaluated_attempts
            for evidence_ref in _candidate_evidence_refs(
                attempt.evaluated,
                revision=attempt.revision,
                attempt_id=attempt.attempt_id,
            )
        )
        if self.development_evidence_refs != expected_evidence_refs:
            raise ValueError("checkpoint development_evidence_refs must match exact trial evidence")
        if self.terminal_result is not None:
            if self.terminal_result.usage != self.usage:
                raise ValueError("checkpoint terminal result usage must match checkpoint usage")
            if self.terminal_result.status is VariationStatus.SUBMITTED:
                assert self.terminal_result.child is not None
                assert self.terminal_result.attempt_id is not None
                if self.terminal_result.child.candidate_id != self.final_child_candidate_id:
                    raise ValueError("checkpoint terminal child must match final_child_candidate_id")
                selected_attempt = next(
                    (item for item in self.evaluated_attempts if item.attempt_id == self.terminal_result.attempt_id),
                    None,
                )
                if selected_attempt is None:
                    raise ValueError("checkpoint terminal attempt_id must reference an attempt")
                if selected_attempt.revision != self.current_revision:
                    raise ValueError("checkpoint terminal attempt must match current_revision")
                if (
                    selected_attempt.evaluated.snapshot.system_prompt != self.terminal_result.child.system_prompt
                    or selected_attempt.evaluated.snapshot.skills != self.terminal_result.child.skills
                ):
                    raise ValueError("checkpoint terminal child must match exact evaluated attempt material")
                if (
                    self.current_snapshot.system_prompt != self.terminal_result.child.system_prompt
                    or self.current_snapshot.skills != self.terminal_result.child.skills
                ):
                    raise ValueError("checkpoint terminal child must match exact current material")
                if _same_workspace_material(self.parent_snapshot, self.terminal_result.child):
                    raise ValueError("checkpoint submitted child must differ from exact parent material")
                if selected_attempt.mutation != self.terminal_result.mutation:
                    raise ValueError("checkpoint terminal mutation must match exact evaluated attempt mutation")
        return self

    @classmethod
    def from_state(
        cls,
        *,
        run_id: str,
        state: AVOState,
        parent_evidence: EvaluatedCandidate | None,
        selection: SelectionRecord,
        development_case_ids: tuple[str, ...],
        configuration_identity: AVOConfigurationIdentity,
        budget: AVOBudget,
        current_snapshot: WorkspaceSnapshot,
        structured_memory: tuple[AVOMemoryEntry, ...] | None = None,
        incomplete_external_effects: tuple[AVOIncompleteExternalEffect, ...] = (),
        terminal_result: AVOCheckpointTerminalResult | None = None,
    ) -> AVOCheckpoint:
        """Project explicit runtime state into the durable contract."""

        if state.parent_snapshot is None:
            raise ValueError("AVOState must contain parent_snapshot for checkpointing")
        state_memory = validate_memory_entries(state.memory)
        if structured_memory is None:
            structured_memory = state_memory
        else:
            structured_memory = validate_memory_entries(structured_memory)
            if structured_memory != state_memory:
                raise ValueError("checkpoint structured_memory must match AVOState memory")
        if state.terminal_status is None:
            if terminal_result is not None:
                raise ValueError("checkpoint terminal result requires matching AVOState terminal_status")
        elif terminal_result is None:
            raise ValueError("AVOState terminal_status requires a checkpoint terminal result")
        elif state.terminal_status is not terminal_result.status:
            raise ValueError("checkpoint terminal result status must match AVOState terminal_status")
        parent_record = (
            None
            if parent_evidence is None
            else AVOCheckpointEvaluatedCandidate.from_evaluated_candidate(parent_evidence)
        )
        attempt_records = tuple(AVOCheckpointAttempt.from_attempt(item) for item in state.attempts)
        run_manifests: dict[str, RunManifest] = {}
        for candidate in (
            *((parent_evidence,) if parent_evidence is not None else ()),
            *(item.evaluated for item in state.attempts),
        ):
            for observation in candidate.observations:
                manifest = observation.trial.run_manifest
                existing = run_manifests.get(manifest.run_id)
                if existing is not None and existing != manifest:
                    raise ValueError("checkpoint evidence run_id resolves to different RunManifest content")
                run_manifests[manifest.run_id] = manifest
        return cls(
            run_id=run_id,
            variation_id=state.variation_id,
            parent_candidate_id=state.parent_candidate_id,
            final_child_candidate_id=state.child_candidate_id,
            selection=selection,
            development_case_ids=development_case_ids,
            development_evidence_refs=(
                (() if parent_record is None else _candidate_evidence_refs(parent_record, revision=0, attempt_id=None))
                + tuple(
                    evidence_ref
                    for attempt in attempt_records
                    for evidence_ref in _candidate_evidence_refs(
                        attempt.evaluated,
                        revision=attempt.revision,
                        attempt_id=attempt.attempt_id,
                    )
                )
            ),
            configuration_identity=configuration_identity,
            parent_snapshot=state.parent_snapshot,
            parent_evidence=parent_record,
            current_revision=state.current_revision,
            current_snapshot=current_snapshot,
            run_manifests=run_manifests,
            evaluated_attempts=attempt_records,
            best_attempt_id=state.best_attempt_id,
            consecutive_without_progress=state.consecutive_without_progress,
            consecutive_evaluation_errors=state.consecutive_evaluation_errors,
            exhausted_direction_requested=state.exhausted_direction_requested,
            budget=AVOBudgetSnapshot.from_budget(budget),
            usage=AVOUsageSnapshot.from_usage(state.usage),
            structured_memory=structured_memory,
            supervision_records=tuple(state.supervision_records),
            incomplete_external_effects=incomplete_external_effects,
            terminal_result=terminal_result,
        )

    def to_state(self) -> AVOState:
        """Restore explicit AVO state values without consulting an event log."""

        return AVOState(
            variation_id=self.variation_id,
            parent_candidate_id=self.parent_candidate_id,
            child_candidate_id=self.final_child_candidate_id,
            current_revision=self.current_revision,
            attempts=tuple(item.to_attempt() for item in self.evaluated_attempts),
            best_attempt_id=self.best_attempt_id,
            consecutive_without_progress=self.consecutive_without_progress,
            consecutive_evaluation_errors=self.consecutive_evaluation_errors,
            exhausted_direction_requested=self.exhausted_direction_requested,
            supervision_records=self.supervision_records,
            memory=self.structured_memory,
            usage=self.usage.to_usage(),
            terminal_status=self.terminal_result.status if self.terminal_result is not None else None,
            parent_snapshot=self.parent_snapshot,
        )


def write_checkpoint(path: Path, checkpoint: AVOCheckpoint) -> Path:
    """Durably replace one checkpoint document with validated JSON bytes."""

    if not isinstance(checkpoint, AVOCheckpoint):
        raise TypeError("checkpoint must be an AVOCheckpoint")
    selected_path = Path(path)
    mkdir_durable(selected_path.parent)
    payload = (
        json.dumps(
            checkpoint.model_dump(mode="json"),
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    replace_file_bytes_durable(selected_path.parent, selected_path.name, payload, host_private=True)
    return selected_path


def read_checkpoint(path: Path) -> AVOCheckpoint:
    """Read and validate the only supported checkpoint schema."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("AVO checkpoint must contain a JSON object")
    schema_version = payload.get("schema_version")
    if schema_version != AVO_CHECKPOINT_SCHEMA_VERSION:
        raise AVOCheckpointCompatibilityError(f"unsupported AVO checkpoint schema_version: {schema_version!r}")
    return AVOCheckpoint.model_validate(payload)


# ``AVOCheckpointAttempt`` refers to the usage model declared below it in the
# source file. Resolve that forward reference once all contract types exist.
AVOCheckpointAttempt.model_rebuild()


__all__ = (
    "AVO_CHECKPOINT_SCHEMA_VERSION",
    "AVOBudgetSnapshot",
    "AVOCheckpoint",
    "AVOCheckpointAttempt",
    "AVOCheckpointCompatibilityError",
    "AVOCheckpointEnrichment",
    "AVOCheckpointEvidenceRef",
    "AVOCheckpointEvaluatedCandidate",
    "AVOCheckpointObservation",
    "AVOCheckpointStructuralScore",
    "AVOCheckpointTerminalResult",
    "AVOCheckpointTrace",
    "AVOCheckpointTurn",
    "AVOConfigurationIdentity",
    "AVOExternalEffectOperation",
    "AVOIncompleteExternalEffect",
    "AVOIncompleteExternalEffectError",
    "AVOSupervisionRecord",
    "AVOUsageSnapshot",
    "read_checkpoint",
    "write_checkpoint",
)
