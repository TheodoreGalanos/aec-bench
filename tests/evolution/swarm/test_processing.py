# ABOUTME: Provider-free tests for host-owned swarm evaluation and archive effects.
# ABOUTME: Proves exact candidate material, validity, insertion, and graveyard boundaries.

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from aec_bench.contracts.evaluation_result import EvaluationResult, ValidityCheck
from aec_bench.contracts.evolution import (
    BehaviourDescriptor,
    CandidateAssessment,
    EvolutionObservation,
    MutationStrategy,
    MutationSummary,
    ObservationEnrichment,
    SkillEntry,
    VariationUsage,
    WorkspaceSnapshot,
)
from aec_bench.contracts.experiment_manifest import AgentConfig, ComputeConfig
from aec_bench.evolution.archive import ArchiveInsertionStatus, QDArchive
from aec_bench.evolution.core import DevelopmentAttempt, SelectionPlan, VariationResult, VariationStatus
from aec_bench.evolution.evaluation import CandidateEvaluationBatch, bind_evaluated_candidate
from aec_bench.evolution.swarm.core import AgentBudget, SwarmAgentResult, SwarmAssignment
from aec_bench.evolution.swarm.processing import (
    evaluate_swarm_result,
    process_swarm_result,
)
from aec_bench.evolution.swarm.shared_graveyard import SharedGraveyard
from aec_bench.tasks.instance import resolve_instance_paths
from aec_bench.trials import PlannedTrial
from tests.support.task_factories import make_task_definition
from tests.support.trial_record_factories import make_trial_record

_NOW = datetime(2026, 8, 26, tzinfo=UTC)


def _batch(tmp_path: Path, count: int = 1) -> CandidateEvaluationBatch:
    tasks = []
    trials = []
    for index in range(count):
        task_id = f"electrical/check/case-{index}"
        task_dir = tmp_path / f"task-{index}"
        task_dir.mkdir(parents=True)
        tasks.append(resolve_instance_paths(make_task_definition(task_id=task_id), task_dir))
        trials.append(
            PlannedTrial(
                trial_id=f"planned-{index}",
                experiment_id="swarm-test",
                task_id=task_id,
                agent=AgentConfig(name="agent", adapter="direct", model="test"),
                compute=ComputeConfig(backend="local"),
                repetition=1,
            )
        )
    return CandidateEvaluationBatch(
        tasks=tuple(tasks),
        trials=tuple(trials),
        evaluation_case_ids=tuple(f"case-{index}" for index in range(count)),
    )


def _assignment(parent: WorkspaceSnapshot | None = None) -> SwarmAssignment:
    parent = parent or WorkspaceSnapshot(system_prompt="Parent prompt", candidate_id="parent")
    selection = SelectionPlan(
        parent_candidate_id=parent.candidate_id,
        inspiration_candidate_ids=(),
        strategy=MutationStrategy.CONSERVATIVE,
        goal="Improve the selected workspace",
        reasoning="Use the exact assigned parent",
    )
    return SwarmAssignment(
        run_id="run-test",
        assignment_id="assignment-1",
        agent_id="agent-1",
        selection=selection,
        parent=parent,
        inspirations=(),
        budget=AgentBudget(max_cost_usd=1.0),
        issued_at=_NOW,
    )


def _result(assignment: SwarmAssignment, child: WorkspaceSnapshot | None) -> SwarmAgentResult:
    usage = VariationUsage(
        model_requests=1,
        development_evaluations=1 if child is not None else 0,
        model_cost_usd=0.1,
        development_evaluation_cost_usd=0.1 if child is not None else None,
    )
    attempt = None
    if child is not None:
        trial = make_trial_record(trial_id=f"{child.candidate_id}-development-trial")
        observation = EvolutionObservation(
            trial=trial,
            enrichment=ObservationEnrichment(),
            candidate_id=child.candidate_id,
            discipline="structural",
        )
        assessment = CandidateAssessment(
            candidate_id=child.candidate_id,
            batch_score=0.5,
            structural_score=None,
            discipline_scores={"structural": 0.5},
            trial_ids=(trial.trial_id,),
            evaluation_case_ids=("case-0",),
            valid=True,
        )
        evaluated = bind_evaluated_candidate(child, (observation,), assessment)
        attempt = DevelopmentAttempt(
            attempt_id=f"{assignment.assignment_id}:attempt-1",
            revision=1,
            evaluated=evaluated,
            mutation=MutationSummary(prompt_modified=True),
            hypothesis="Apply the proposed prompt change",
            usage_after=usage,
        )
    variation = VariationResult(
        status=VariationStatus.SUBMITTED if child is not None else VariationStatus.ABSTAINED,
        child=child,
        mutation=MutationSummary(prompt_modified=True) if child is not None else None,
        reasoning="Apply the proposed prompt change",
        usage=usage,
        attempt=attempt,
    )
    return SwarmAgentResult(
        agent_id=assignment.agent_id,
        assignment_id=assignment.assignment_id,
        variation=variation,
        agent_usage=usage,
    )


def _evaluator(rewards: dict[str, float] | None = None, invalid: set[str] | None = None):
    rewards = rewards or {}
    invalid = invalid or set()

    def evaluate(snapshot: WorkspaceSnapshot, batch: CandidateEvaluationBatch):
        return tuple(
            make_trial_record(
                trial_id=f"{snapshot.candidate_id}-trial-{index}",
                task_id=trial.task_id,
                evaluation=EvaluationResult(
                    reward=0.0 if snapshot.candidate_id in invalid else rewards.get(snapshot.candidate_id, 0.5),
                    validity=ValidityCheck(
                        output_parseable=snapshot.candidate_id not in invalid,
                        schema_valid=True,
                        verifier_completed=True,
                        errors=("output was invalid",) if snapshot.candidate_id in invalid else (),
                    ),
                ),
            )
            for index, trial in enumerate(batch.trials)
        )

    return evaluate


def _identity_enricher(observations):
    return observations


def _process(
    tmp_path: Path,
    *,
    child: WorkspaceSnapshot | None,
    batch_count: int = 1,
    evaluate=None,
    archive: QDArchive | None = None,
    graveyard: SharedGraveyard | None = None,
):
    assignment = _assignment()
    result = _result(assignment, child)
    return process_swarm_result(
        assignment=assignment,
        agent_result=result,
        batch=_batch(tmp_path, batch_count),
        evaluate=evaluate or _evaluator(),
        enrich=_identity_enricher,
        archive=archive or QDArchive(n_centroids=20),
        graveyard=graveyard or SharedGraveyard(),
        run_id="run-1",
        cycle=3,
        now=_NOW,
    )


def test_no_child_skips_evaluation_archive_and_graveyard(tmp_path: Path) -> None:
    def fail_evaluate(snapshot: WorkspaceSnapshot, batch: CandidateEvaluationBatch):
        raise AssertionError("an abstention must not be evaluated")

    archive = QDArchive(n_centroids=20)
    graveyard = SharedGraveyard()
    outcome = _process(tmp_path, child=None, evaluate=fail_evaluate, archive=archive, graveyard=graveyard)
    assert outcome.evaluated_candidate is None
    assert outcome.archive_outcome is None
    assert archive.size == 0
    assert graveyard.size == 0


def test_identity_mismatch_fails_before_evaluation_or_effects(tmp_path: Path) -> None:
    assignment = _assignment()
    mismatched = SwarmAgentResult(
        agent_id=assignment.agent_id,
        assignment_id="other-assignment",
        variation=_result(assignment, None).variation,
        agent_usage=_result(assignment, None).agent_usage,
    )
    calls: list[str] = []
    archive = QDArchive(n_centroids=20)
    graveyard = SharedGraveyard()
    with pytest.raises(ValueError, match="assignment_id"):
        process_swarm_result(
            assignment=assignment,
            agent_result=mismatched,
            batch=_batch(tmp_path),
            evaluate=lambda snapshot, batch: calls.append(snapshot.candidate_id) or (),
            enrich=_identity_enricher,
            archive=archive,
            graveyard=graveyard,
            run_id="run-1",
            cycle=3,
            now=_NOW,
        )
    assert calls == []
    assert archive.size == 0
    assert graveyard.size == 0


def test_child_with_non_submitted_status_fails_before_effects(tmp_path: Path) -> None:
    assignment = _assignment()
    child = WorkspaceSnapshot(system_prompt="Child", candidate_id="child")
    # Construct a malformed boundary value to keep the host-side validation
    # regression. Normal VariationResult construction rejects this shape.
    variation = object.__new__(VariationResult)
    object.__setattr__(variation, "status", VariationStatus.BUDGET_EXHAUSTED)
    object.__setattr__(variation, "child", child)
    object.__setattr__(variation, "mutation", None)
    object.__setattr__(variation, "reasoning", "Budget ended after material was returned")
    object.__setattr__(variation, "usage", VariationUsage(model_requests=1, model_cost_usd=0.1))
    object.__setattr__(variation, "attempt", None)
    result = SwarmAgentResult(
        agent_id=assignment.agent_id,
        assignment_id=assignment.assignment_id,
        variation=variation,
        agent_usage=variation.usage,
    )
    archive = QDArchive(n_centroids=20)
    graveyard = SharedGraveyard()
    with pytest.raises(ValueError, match="submitted variation status"):
        process_swarm_result(
            assignment=assignment,
            agent_result=result,
            batch=_batch(tmp_path),
            evaluate=_evaluator(),
            enrich=_identity_enricher,
            archive=archive,
            graveyard=graveyard,
            run_id="run-1",
            cycle=3,
            now=_NOW,
        )
    assert archive.size == 0
    assert graveyard.size == 0


def test_parent_and_child_use_the_same_explicit_batch(tmp_path: Path) -> None:
    child = WorkspaceSnapshot(system_prompt="Child prompt", candidate_id="child")
    batch = _batch(tmp_path)
    calls: list[tuple[str, CandidateEvaluationBatch]] = []

    def evaluate(snapshot: WorkspaceSnapshot, candidate_batch: CandidateEvaluationBatch):
        calls.append((snapshot.candidate_id, candidate_batch))
        return _evaluator()(snapshot, candidate_batch)

    assignment = _assignment()
    evaluation = evaluate_swarm_result(
        assignment=assignment,
        agent_result=_result(assignment, child),
        batch=batch,
        evaluate=evaluate,
        enrich=_identity_enricher,
        run_id="run-1",
        cycle=3,
        now=_NOW,
    )
    assert calls == [("parent", batch), ("child", batch)]
    assert evaluation.parent is not None
    assert evaluation.child is not None
    assert evaluation.parent.assessment.evaluation_case_ids == evaluation.child.assessment.evaluation_case_ids


def test_child_evidence_and_archive_keep_exact_snapshot_material(tmp_path: Path) -> None:
    child = WorkspaceSnapshot(
        system_prompt="Actual child prompt",
        skills=(SkillEntry(name="child-skill", description="Child skill", body="Use this skill"),),
        candidate_id="child",
    )
    archive = QDArchive(n_centroids=20)
    graveyard = SharedGraveyard()
    outcome = _process(tmp_path, child=child, archive=archive, graveyard=graveyard)
    assert outcome.evaluated_candidate is not None
    assert outcome.evaluated_candidate.snapshot is child
    entry = archive.view().get_entry_by_candidate_id("child")
    assert entry is not None
    assert entry.snapshot is child
    assert entry.snapshot.system_prompt == "Actual child prompt"
    assert entry.snapshot.skills == child.skills


def test_invalid_child_is_graveyarded_exactly_once_without_archive_effect(tmp_path: Path) -> None:
    child = WorkspaceSnapshot(system_prompt="Invalid child", candidate_id="child")
    archive = QDArchive(n_centroids=20)
    graveyard = SharedGraveyard()
    outcome = _process(
        tmp_path,
        child=child,
        evaluate=_evaluator(invalid={"child"}),
        archive=archive,
        graveyard=graveyard,
    )
    assert outcome.evaluated_candidate is not None
    assert outcome.evaluated_candidate.assessment.valid is False
    assert outcome.archive_outcome is None
    assert archive.size == 0
    entries = graveyard.browse_all()
    assert len(entries) == 1
    assert entries[0].rejected_snapshot is child
    assert entries[0].parent_assessment is not None
    assert entries[0].child_assessment is outcome.evaluated_candidate.assessment
    assert entries[0].mutation is not None


def test_valid_child_that_does_not_enter_archive_is_graveyarded(tmp_path: Path) -> None:
    child = WorkspaceSnapshot(system_prompt="Child", candidate_id="child")
    archive = QDArchive(n_centroids=20)
    existing = WorkspaceSnapshot(system_prompt="Existing", candidate_id="existing")
    archive.insert(
        bd=BehaviourDescriptor(
            token_cost=0,
            verification_depth=0,
            tool_density=0,
            exploration_ratio=0,
            deliberation_ratio=0,
            reward=0.9,
        ),
        snapshot=existing,
    )
    graveyard = SharedGraveyard()
    outcome = _process(tmp_path, child=child, archive=archive, graveyard=graveyard)
    assert outcome.archive_outcome is not None
    assert all(item.status is ArchiveInsertionStatus.NOT_ADDED for item in outcome.archive_outcome.insertions)
    assert graveyard.size == 1
    assert graveyard.browse_all()[0].rejected_snapshot is child


def test_accepted_child_is_not_graveyarded_and_reports_explicit_status(tmp_path: Path) -> None:
    child = WorkspaceSnapshot(system_prompt="Accepted child", candidate_id="child")
    archive = QDArchive(n_centroids=20)
    graveyard = SharedGraveyard()
    outcome = _process(tmp_path, child=child, archive=archive, graveyard=graveyard)
    assert outcome.archive_outcome is not None
    assert outcome.archive_outcome.insertions[0].status is ArchiveInsertionStatus.NEW_CELL
    assert outcome.archive_outcome.added is True
    assert graveyard.size == 0


def test_multiple_descriptors_return_one_batch_outcome(tmp_path: Path) -> None:
    child = WorkspaceSnapshot(system_prompt="Child", candidate_id="child")
    archive = QDArchive(n_centroids=20)
    outcome = _process(tmp_path, child=child, batch_count=2, archive=archive)
    assert outcome.archive_outcome is not None
    assert len(outcome.archive_outcome.insertions) == 2
    assert all(item.candidate_id == "child" for item in outcome.archive_outcome.insertions)
