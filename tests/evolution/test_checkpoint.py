# ABOUTME: Tests the durable AVO checkpoint contract and its exact evidence identity.
# ABOUTME: Proves schema rejection, crash-safe publication, and snapshot/evidence consistency.

from __future__ import annotations

import json
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
    SelectionRecord,
    VariationUsage,
    WorkspaceSnapshot,
)
from aec_bench.evolution.checkpoint import (
    AVOBudgetSnapshot,
    AVOCheckpoint,
    AVOCheckpointCompatibilityError,
    AVOCheckpointTerminalResult,
    AVOConfigurationIdentity,
    AVOUsageSnapshot,
    read_checkpoint,
    write_checkpoint,
)
from aec_bench.evolution.core import AVOState, DevelopmentAttempt, EvaluatedCandidate, VariationStatus
from aec_bench.evolution.development import DevelopmentEvaluationProvenance
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
        DevelopmentEvaluationProvenance(
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
    terminal_status: VariationStatus | None = None,
    terminal_result: AVOCheckpointTerminalResult | None = None,
) -> AVOCheckpoint:
    attempt = DevelopmentAttempt(
        attempt_id="attempt-1",
        revision=1,
        evaluated=_candidate(with_artifact=with_artifact),
        mutation=MutationSummary(prompt_modified=True),
        hypothesis="Improve the prompt.",
        usage_after=VariationUsage(development_evaluations=1),
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
        usage=VariationUsage(development_evaluations=1),
        terminal_status=terminal_status,
        parent_snapshot=parent,
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
            tool_identity="avo-tools:1",
            development_evaluator_identity="evaluator:1",
            configuration_identity="config:1",
        ),
        budget=AVOBudgetSnapshot().to_budget(),
        current_snapshot=current_snapshot or WorkspaceSnapshot(system_prompt="Child prompt", candidate_id="child"),
        terminal_result=terminal_result,
    )


def _validated_update(checkpoint: AVOCheckpoint, **updates: object) -> AVOCheckpoint:
    payload = checkpoint.model_dump(mode="python")
    payload.update(updates)
    return AVOCheckpoint.model_validate(payload)


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
    assert isinstance(provenance, DevelopmentEvaluationProvenance)
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


@pytest.mark.parametrize("schema_version", [None, 0, 2, "1"])
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
        status=VariationStatus.SUBMITTED,
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
            status=VariationStatus.ABSTAINED,
            reasoning="No useful mutation was found.",
            usage=AVOUsageSnapshot(),
            child=WorkspaceSnapshot(system_prompt="Child prompt", candidate_id="child"),
        )


def test_checkpoint_from_state_requires_terminal_status_to_match_result() -> None:
    terminal = AVOCheckpointTerminalResult(
        status=VariationStatus.SUBMITTED,
        reasoning="Submit the evaluated revision.",
        usage=AVOUsageSnapshot(development_evaluations=1),
        child=WorkspaceSnapshot(system_prompt="Child prompt", candidate_id="child"),
        mutation=MutationSummary(prompt_modified=True),
        attempt_id="attempt-1",
    )

    with pytest.raises(ValueError, match="terminal result requires matching AVOState terminal_status"):
        _checkpoint(terminal_result=terminal)

    with pytest.raises(ValueError, match="AVOState terminal_status requires a checkpoint terminal result"):
        _checkpoint(terminal_status=VariationStatus.SUBMITTED)

    checkpoint = _checkpoint(terminal_status=VariationStatus.SUBMITTED, terminal_result=terminal)
    assert checkpoint.terminal_result == terminal


def test_checkpoint_preserves_unknown_cost_and_typed_memory() -> None:
    checkpoint = _validated_update(
        _checkpoint(),
        usage=AVOUsageSnapshot(model_requests=1, development_evaluations=1),
        structured_memory=(
            {
                "source_variation_id": "variation-1",
                "source_attempt_id": "attempt-1",
                "category": "direction",
                "summary": "Use stronger checks.",
            },
        ),
    )

    assert checkpoint.usage.model_cost_usd is None
    assert checkpoint.structured_memory[0].source_attempt_id == "attempt-1"


def test_checkpoint_rejects_more_than_24_memory_entries() -> None:
    entries = tuple(
        {
            "source_variation_id": "variation-1",
            "source_attempt_id": "attempt-1",
            "category": f"failure-{index}",
            "summary": "Keep the evidence exact.",
        }
        for index in range(25)
    )

    with pytest.raises(ValidationError, match="structured_memory must contain at most 24 entries"):
        _validated_update(_checkpoint(), structured_memory=entries)
