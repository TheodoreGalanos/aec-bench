# ABOUTME: Tests the durable AVO checkpoint contract and its exact evidence identity.
# ABOUTME: Proves schema rejection, crash-safe publication, and snapshot/evidence consistency.

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
from pydantic import ValidationError

from aec_bench.contracts.behavioral_types import BondType, ClassifiedTrace, StructuralScore, TurnClassification
from aec_bench.contracts.evolution import (
    CandidateAssessment,
    EvolutionObservation,
    MutationStrategy,
    MutationSummary,
    ObservationEnrichment,
    ProposalUsage,
    SelectionRecord,
    WorkspaceSnapshot,
)
from aec_bench.evolution.advice import (
    AVOAdvice,
    AVOAdviceFailure,
    AVOAdviceFailureCode,
    AVOAdviceRecord,
    AVOAdviceTrigger,
)
from aec_bench.evolution.checkpoint import (
    AVOBudgetSnapshot,
    AVOCheckpoint,
    AVOCheckpointCompatibilityError,
    AVOCheckpointTerminalResult,
    AVOConfigurationIdentity,
    AVOIncompleteExternalEffect,
    AVOUsageSnapshot,
    read_checkpoint,
    write_checkpoint,
)
from aec_bench.evolution.core import AVOState, EvaluatedCandidate, ProposalStatus, RevisionAttempt
from aec_bench.evolution.revision import RevisionEvaluationProvenance
from tests.support.trial_record_factories import make_trial_record


def _candidate(
    candidate_id: str = "child:revision-1",
    *,
    trial_id: str = "trial-1",
    prompt: str = "Child prompt",
    revision: int = 1,
    with_artifact: bool = False,
) -> EvaluatedCandidate:
    inputs = None
    if with_artifact:
        inputs = {
            "instruction": "Review the task and write output.",
            "task_revision": "git-sha-task",
            "visibility": "public",
            "system_prompt": "Use tools carefully.",
            "input_files": [
                {
                    "artifact": {
                        "artifact_id": "input.txt",
                        "sha256": "a" * 64,
                        "size_bytes": 3,
                        "media_type": "text/plain",
                    },
                    "source": "fixture",
                }
            ],
        }
    trial = (
        make_trial_record(trial_id=trial_id, inputs=inputs)
        if inputs is not None
        else make_trial_record(trial_id=trial_id)
    )
    trial.attach_extension(
        "development_evaluation",
        RevisionEvaluationProvenance(
            experiment_id=trial.experiment_id,
            trial_id=trial.trial_id,
            candidate_id=candidate_id,
            revision=revision,
            evaluation_case_id="case-1",
        ),
    )
    trial.attach_extension("diagnostic", {"source": "fixture"})
    observation = EvolutionObservation(
        trial=trial,
        enrichment=ObservationEnrichment(
            classified_trace=ClassifiedTrace(
                trace_id="trace-1",
                model_name="model",
                classifications=(TurnClassification(1, BondType.EXECUTION, 0.9, "checked"),),
                metadata={"source": "development"},
            ),
            structural_score=StructuralScore("trace-1", 0.8, 2, 0.2, 0.5),
        ),
        candidate_id=candidate_id,
        discipline="electrical",
    )
    assessment = CandidateAssessment(
        candidate_id=candidate_id,
        batch_score=0.5,
        discipline_scores={"electrical": 0.5},
        trial_ids=(trial_id,),
        evaluation_case_ids=("case-1",),
        valid=True,
    )
    return EvaluatedCandidate(
        snapshot=WorkspaceSnapshot(system_prompt=prompt, candidate_id=candidate_id),
        observations=(observation,),
        assessment=assessment,
    )


def _checkpoint(
    *,
    current_revision: int = 1,
    current_snapshot: WorkspaceSnapshot | None = None,
    with_artifact: bool = False,
    terminal_status: ProposalStatus | None = None,
    terminal_result: AVOCheckpointTerminalResult | None = None,
    supervision_records: tuple[AVOAdviceRecord, ...] = (),
    exhausted_direction_requested: bool = False,
    max_supervisor_interventions: int = 1,
) -> AVOCheckpoint:
    attempt = RevisionAttempt(
        attempt_id="attempt-1",
        revision=1,
        evaluated=_candidate(with_artifact=with_artifact),
        mutation=MutationSummary(prompt_modified=True),
        hypothesis="Improve the prompt.",
        usage_after=ProposalUsage(development_evaluations=1),
    )
    parent = WorkspaceSnapshot(system_prompt="Parent prompt", candidate_id="parent")
    parent_evidence = _candidate(
        "parent",
        trial_id="parent-trial",
        prompt="Parent prompt",
        revision=0,
        with_artifact=with_artifact,
    )
    state = AVOState(
        variation_id="variation-1",
        parent_candidate_id="parent",
        child_candidate_id="child",
        current_revision=current_revision,
        attempts=(attempt,),
        best_attempt_id="attempt-1",
        usage=ProposalUsage(
            development_evaluations=1,
            supervisor_interventions=len(supervision_records),
        ),
        terminal_status=terminal_status,
        parent_snapshot=parent,
        supervision_records=supervision_records,
        exhausted_direction_requested=exhausted_direction_requested,
    )
    return AVOCheckpoint.from_state(
        run_id="run-1",
        state=state,
        parent_evidence=parent_evidence,
        selection=SelectionRecord(
            parent_candidate_id="parent",
            strategy=MutationStrategy.CONSERVATIVE,
            goal="Improve checks",
            reasoning="The parent needs stronger checks.",
        ),
        development_case_ids=("case-1",),
        configuration_identity=AVOConfigurationIdentity(
            model_identity="provider:model",
            supervisor_model_identity="provider:supervisor-model",
            tool_identity="avo-tools:1",
            development_evaluator_identity="evaluator:1",
            configuration_identity="config:1",
        ),
        budget=AVOBudgetSnapshot(max_supervisor_interventions=max_supervisor_interventions).to_budget(),
        current_snapshot=current_snapshot or WorkspaceSnapshot(system_prompt="Child prompt", candidate_id="child"),
        terminal_result=terminal_result,
    )


def _validated_update(checkpoint: AVOCheckpoint, **updates: object) -> AVOCheckpoint:
    payload = checkpoint.model_dump(mode="python")
    payload.update(updates)
    return AVOCheckpoint.model_validate(payload)


def test_checkpoint_snapshots_round_trip_supervisor_identity_tokens_and_limits() -> None:
    usage = ProposalUsage(
        model_requests=2,
        supervisor_interventions=1,
        input_tokens=120,
        output_tokens=30,
        model_cost_usd=0.6,
    )
    budget = AVOBudgetSnapshot(
        max_input_tokens=200,
        max_output_tokens=60,
        max_supervisor_interventions=1,
    ).to_budget()
    identity = AVOConfigurationIdentity(
        model_identity="provider:main",
        supervisor_model_identity="provider:supervisor",
        tool_identity="avo-tools:1",
        development_evaluator_identity="evaluator:1",
        configuration_identity="config:1",
    )

    assert AVOUsageSnapshot.from_usage(usage).to_usage() == usage
    assert AVOBudgetSnapshot.from_budget(budget).to_budget() == budget
    assert identity.model_dump(mode="json")["supervisor_model_identity"] == "provider:supervisor"


@pytest.mark.parametrize(
    "record",
    [
        AVOAdviceRecord(
            trigger_reason=AVOAdviceTrigger.VALID_DEVELOPMENT_STAGNATION,
            advice=AVOAdvice(
                directions=("Use a narrower verification path.",),
                reasoning="The latest valid attempts repeat the same direction.",
            ),
        ),
        AVOAdviceRecord(
            trigger_reason=AVOAdviceTrigger.CONSECUTIVE_INVALID_OR_FAILED_EVALUATIONS,
            failure=AVOAdviceFailure(
                code=AVOAdviceFailureCode.OUTPUT_VALIDATION_REJECTED,
                detail="The supervisor output was not valid advice.",
            ),
        ),
    ],
)
def test_checkpoint_round_trips_ordered_supervision_outcome_and_pending_request(
    record: AVOAdviceRecord,
    tmp_path: Path,
) -> None:
    checkpoint = _checkpoint(supervision_records=(record,))
    path = write_checkpoint(tmp_path / "avo.json", checkpoint)
    restored = read_checkpoint(path)

    assert restored.supervision_records == (record,)
    assert restored.to_state().supervision_records == (record,)
    assert restored.model_dump(mode="json") == read_checkpoint(path).model_dump(mode="json")

    pending = _checkpoint(exhausted_direction_requested=True)
    assert pending.exhausted_direction_requested is True
    assert pending.to_state().exhausted_direction_requested is True


def test_checkpoint_preserves_ordered_supervision_history_within_explicit_budget() -> None:
    first = AVOAdviceRecord(
        trigger_reason=AVOAdviceTrigger.VALID_DEVELOPMENT_STAGNATION,
        advice=AVOAdvice(directions=("Try direction one.",), reasoning="First intervention."),
    )
    second = AVOAdviceRecord(
        trigger_reason=AVOAdviceTrigger.EXHAUSTED_DIRECTION_REQUEST,
        advice=AVOAdvice(directions=("Try direction two.",), reasoning="Second intervention."),
    )
    checkpoint = _checkpoint(
        supervision_records=(first, second),
        max_supervisor_interventions=2,
    )

    assert checkpoint.supervision_records == (first, second)
    assert checkpoint.to_state().supervision_records == (first, second)


def test_checkpoint_rejects_supervision_history_over_budget() -> None:
    first = AVOAdviceRecord(
        trigger_reason=AVOAdviceTrigger.VALID_DEVELOPMENT_STAGNATION,
        advice=AVOAdvice(directions=("Try direction one.",), reasoning="First intervention."),
    )
    second = AVOAdviceRecord(
        trigger_reason=AVOAdviceTrigger.EXHAUSTED_DIRECTION_REQUEST,
        advice=AVOAdvice(directions=("Try direction two.",), reasoning="Second intervention."),
    )

    with pytest.raises(ValidationError, match="exceed the configured supervisor intervention budget"):
        _checkpoint(supervision_records=(first, second))


def test_checkpoint_rejects_supervision_usage_without_outcome_or_incomplete_request() -> None:
    checkpoint = _checkpoint()
    with pytest.raises(ValidationError, match="supervision_records and incomplete requests"):
        _validated_update(
            checkpoint,
            usage=AVOUsageSnapshot.from_usage(ProposalUsage(model_requests=1, supervisor_interventions=1)),
        )


def test_checkpoint_accepts_one_incomplete_supervisor_request_before_outcome() -> None:
    checkpoint = _checkpoint(exhausted_direction_requested=True)
    pending_effect = AVOIncompleteExternalEffect(
        effect_id="variation-1:supervisor-1",
        operation="supervisor_request",
        reason="Supervisor request started; completion is not yet confirmed.",
    )
    resumed_shape = _validated_update(
        checkpoint,
        usage=AVOUsageSnapshot.from_usage(ProposalUsage(model_requests=1, supervisor_interventions=1)),
        incomplete_external_effects=(pending_effect,),
    )

    assert resumed_shape.incomplete_external_effects == (pending_effect,)


def test_checkpoint_rejects_pending_direction_after_supervisor_budget_is_consumed() -> None:
    record = AVOAdviceRecord(
        trigger_reason=AVOAdviceTrigger.EXHAUSTED_DIRECTION_REQUEST,
        advice=AVOAdvice(directions=("Try a bounded alternative.",), reasoning="The first direction stalled."),
    )

    with pytest.raises(ValidationError, match="cannot remain after supervisor budget is consumed"):
        _checkpoint(
            supervision_records=(record,),
            exhausted_direction_requested=True,
            max_supervisor_interventions=1,
        )


def test_avo_state_rejects_untyped_or_overcounted_supervision_records() -> None:
    base = _checkpoint().to_state()
    with pytest.raises(TypeError, match="AVOAdviceRecord"):
        replace(base, supervision_records=(object(),))
    with pytest.raises(ValueError, match="cannot exceed supervisor_interventions"):
        replace(
            base,
            supervision_records=(
                AVOAdviceRecord(
                    trigger_reason=AVOAdviceTrigger.EXHAUSTED_DIRECTION_REQUEST,
                    advice=AVOAdvice(
                        directions=("Try a different direction.",),
                        reasoning="The current path is exhausted.",
                    ),
                ),
            ),
        )


@pytest.mark.parametrize("field_name", ["max_input_tokens", "max_output_tokens"])
def test_checkpoint_rejects_non_positive_token_limits(field_name: str) -> None:
    with pytest.raises(ValidationError, match="positive integers"):
        AVOBudgetSnapshot(**{field_name: 0})


def test_checkpoint_round_trips_exact_attempt_evidence_and_trace_enrichment(tmp_path: Path) -> None:
    checkpoint = _checkpoint()

    path = write_checkpoint(tmp_path / "avo.json", checkpoint)
    restored = read_checkpoint(path)

    assert restored.model_dump(mode="json") == checkpoint.model_dump(mode="json")
    assert restored.to_state().attempts[0].evaluated.observations[0].enrichment.classified_trace is not None
    assert restored.to_state().attempts[0].evaluated.observations[0].enrichment.structural_score == StructuralScore(
        "trace-1", 0.8, 2, 0.2, 0.5
    )


def test_checkpoint_round_trips_manifest_and_development_provenance(tmp_path: Path) -> None:
    path = write_checkpoint(tmp_path / "avo.json", _checkpoint())
    restored = read_checkpoint(path)
    observation = restored.parent_evidence.to_evaluated_candidate().observations[0]

    assert observation.trial.experiment_id == "experiment-001"
    provenance = observation.trial.pending_extensions["development_evaluation"]
    assert isinstance(provenance, RevisionEvaluationProvenance)
    assert provenance.revision == 0
    assert provenance.candidate_id == "parent"
    assert observation.trial.pending_extensions["diagnostic"] == {"source": "fixture"}


def test_checkpoint_writer_uses_durable_replacement(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    checkpoint = _checkpoint()
    calls: list[tuple[Path, str, bytes, bool]] = []

    def record_replace(directory: Path, file_name: str, payload: bytes, *, host_private: bool = False) -> None:
        calls.append((directory, file_name, payload, host_private))

    monkeypatch.setattr("aec_bench.evolution.checkpoint.replace_file_bytes_durable", record_replace)

    path = write_checkpoint(tmp_path / "avo.json", checkpoint)

    assert path == tmp_path / "avo.json"
    assert calls and calls[0][0] == tmp_path
    assert calls[0][1] == "avo.json"
    assert calls[0][3] is True
    assert json.loads(calls[0][2]) == checkpoint.model_dump(mode="json")


@pytest.mark.parametrize("schema_version", [None, 0, 1, "2"])
def test_checkpoint_reader_rejects_missing_or_unsupported_schema(schema_version: object, tmp_path: Path) -> None:
    payload = _checkpoint().model_dump(mode="json")
    if schema_version is None:
        payload.pop("schema_version")
    else:
        payload["schema_version"] = schema_version
    path = tmp_path / "avo.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(AVOCheckpointCompatibilityError, match="unsupported AVO checkpoint schema_version"):
        read_checkpoint(path)


def test_checkpoint_rejects_parent_and_current_snapshot_identity_mismatch() -> None:
    checkpoint = _checkpoint()

    with pytest.raises(ValidationError, match="parent_snapshot must match parent_candidate_id"):
        _validated_update(
            checkpoint,
            parent_snapshot=WorkspaceSnapshot(system_prompt="Parent prompt", candidate_id="wrong"),
        )
    with pytest.raises(ValidationError, match="current_snapshot must match final_child_candidate_id"):
        _validated_update(
            checkpoint,
            current_snapshot=WorkspaceSnapshot(system_prompt="Child prompt", candidate_id="wrong"),
        )


def test_checkpoint_rejects_current_material_different_from_evaluated_revision() -> None:
    with pytest.raises(ValidationError, match="current_snapshot must match exact current evaluated attempt material"):
        _checkpoint(current_snapshot=WorkspaceSnapshot(system_prompt="Tampered", candidate_id="child"))


def test_checkpoint_accepts_current_material_for_un_evaluated_revision() -> None:
    checkpoint = _checkpoint(
        current_revision=2,
        current_snapshot=WorkspaceSnapshot(system_prompt="New mutation", candidate_id="child"),
    )

    assert checkpoint.current_revision == 2
    assert checkpoint.current_snapshot.system_prompt == "New mutation"


def test_checkpoint_rejects_tampered_evidence_reference() -> None:
    checkpoint = _checkpoint()
    evidence = checkpoint.development_evidence_refs[0].model_copy(update={"trial_id": "different"})

    with pytest.raises(ValidationError, match="development_evidence_refs must match exact trial evidence"):
        _validated_update(checkpoint, development_evidence_refs=(evidence,))


def test_checkpoint_rejects_tampered_artifact_content_identity() -> None:
    checkpoint = _checkpoint(with_artifact=True)
    evidence = checkpoint.development_evidence_refs[0]
    artifact = evidence.artifact_refs[0].model_copy(update={"sha256": "b" * 64})
    tampered = evidence.model_copy(update={"artifact_refs": (artifact,)})

    with pytest.raises(ValidationError, match="development_evidence_refs must match exact trial evidence"):
        _validated_update(checkpoint, development_evidence_refs=(tampered, *checkpoint.development_evidence_refs[1:]))


def test_checkpoint_rejects_tampered_development_provenance() -> None:
    checkpoint = _checkpoint()
    observation = checkpoint.parent_evidence.observations[0]
    provenance = observation.development_provenance.model_copy(update={"revision": 1})
    tampered_observation = observation.model_copy(update={"development_provenance": provenance})
    tampered_parent = checkpoint.parent_evidence.model_copy(update={"observations": (tampered_observation,)})

    with pytest.raises(ValidationError, match="development provenance"):
        _validated_update(checkpoint, parent_evidence=tampered_parent)


def test_checkpoint_rejects_attempt_case_order_mismatch() -> None:
    checkpoint = _checkpoint()
    attempt = checkpoint.evaluated_attempts[0]
    tampered_assessment = attempt.evaluated.assessment.model_copy(update={"evaluation_case_ids": ("case-2",)})
    tampered_candidate = attempt.evaluated.model_copy(update={"assessment": tampered_assessment})
    tampered_attempt = attempt.model_copy(update={"evaluated": tampered_candidate})

    with pytest.raises(ValidationError, match="evaluation cases must match development_case_ids exactly"):
        _validated_update(checkpoint, evaluated_attempts=(tampered_attempt,))


def test_checkpoint_rejects_terminal_status_and_mutation_mismatch() -> None:
    checkpoint = _checkpoint()
    terminal = AVOCheckpointTerminalResult(
        status=ProposalStatus.SUBMITTED,
        reasoning="Submit the evaluated revision.",
        usage=AVOUsageSnapshot(development_evaluations=1),
        child=WorkspaceSnapshot(system_prompt="Child prompt", candidate_id="child"),
        mutation=MutationSummary(prompt_modified=True),
        attempt_id="attempt-1",
    )

    _validated_update(checkpoint, terminal_result=terminal)

    tampered_terminal = terminal.model_copy(update={"mutation": MutationSummary(prompt_modified=False)})
    with pytest.raises(ValidationError, match="terminal mutation must match exact evaluated attempt mutation"):
        _validated_update(checkpoint, terminal_result=tampered_terminal)

    with pytest.raises(ValidationError, match="abstained checkpoint result must not contain child"):
        AVOCheckpointTerminalResult(
            status=ProposalStatus.ABSTAINED,
            reasoning="No useful mutation was found.",
            usage=AVOUsageSnapshot(),
            child=WorkspaceSnapshot(system_prompt="Child prompt", candidate_id="child"),
        )


def test_checkpoint_from_state_requires_terminal_status_to_match_result() -> None:
    terminal = AVOCheckpointTerminalResult(
        status=ProposalStatus.SUBMITTED,
        reasoning="Submit the evaluated revision.",
        usage=AVOUsageSnapshot(development_evaluations=1),
        child=WorkspaceSnapshot(system_prompt="Child prompt", candidate_id="child"),
        mutation=MutationSummary(prompt_modified=True),
        attempt_id="attempt-1",
    )

    with pytest.raises(ValueError, match="terminal result requires matching AVOState terminal_status"):
        _checkpoint(terminal_result=terminal)

    with pytest.raises(ValueError, match="AVOState terminal_status requires a checkpoint terminal result"):
        _checkpoint(terminal_status=ProposalStatus.SUBMITTED)

    checkpoint = _checkpoint(terminal_status=ProposalStatus.SUBMITTED, terminal_result=terminal)
    assert checkpoint.terminal_result == terminal

    with pytest.raises(ValidationError, match="terminal checkpoint must not retain incomplete external effects"):
        _validated_update(
            checkpoint,
            incomplete_external_effects=(
                AVOIncompleteExternalEffect(
                    effect_id="variation-1:model-1",
                    operation="model_request",
                    reason="Provider completion is not confirmed.",
                ),
            ),
        )


def test_checkpoint_rejects_unknown_external_effect_operation() -> None:
    with pytest.raises(ValidationError, match="model_request"):
        AVOIncompleteExternalEffect(
            effect_id="variation-1:unknown-1",
            operation="unknown",  # type: ignore[arg-type]
            reason="Unknown external operation.",
        )


def test_checkpoint_preserves_unknown_cost_and_typed_memory() -> None:
    checkpoint = _validated_update(
        _checkpoint(),
        usage=AVOUsageSnapshot(model_requests=1, development_evaluations=1),
        structured_memory=(
            {
                "source_variation_id": "variation-1",
                "source_attempt_id": "attempt-1",
                "hypothesis": "Use stronger checks.",
                "change_summary": "system prompt modified",
                "evidence_summary": "valid=True; batch_score=0.5; evaluation_cases=1; trials=1",
                "outcome": "improved",
                "next_direction": "Test the next bounded follow-up.",
            },
        ),
    )

    assert checkpoint.usage.model_cost_usd is None
    assert checkpoint.structured_memory[0].source_attempt_id == "attempt-1"
    assert checkpoint.structured_memory[0].hypothesis == "Use stronger checks."


def test_checkpoint_rejects_more_than_24_memory_entries() -> None:
    entries = tuple(
        {
            "source_variation_id": "variation-1",
            "source_attempt_id": f"attempt-{index}",
            "hypothesis": "Keep the evidence exact.",
            "change_summary": "system prompt modified",
            "evidence_summary": "valid=False; batch_score=0; evaluation_cases=1; trials=1",
            "outcome": "invalid",
            "failure_category": f"failure-{index}",
        }
        for index in range(25)
    )

    with pytest.raises(ValidationError, match="structured_memory must contain at most 24 entries"):
        _validated_update(_checkpoint(), structured_memory=entries)
