# ABOUTME: Tests the bounded development-evaluation boundary for agentic variation.
# ABOUTME: Proves fixed public batches, separate identities, and exact revision evidence binding.

from pathlib import Path

import pytest

from aec_bench.contracts.evolution import MutationSummary, WorkspaceSnapshot
from aec_bench.contracts.experiment_manifest import AgentConfig, ComputeConfig
from aec_bench.contracts.task_definition import Visibility
from aec_bench.evolution.core import VariationUsage
from aec_bench.evolution.development import (
    DevelopmentEvaluationBoundary,
    EvaluationRole,
    make_deterministic_development_batch_planner,
    make_deterministic_development_evaluator,
)
from aec_bench.evolution.evaluation import CandidateEvaluationBatch
from aec_bench.tasks.instance import resolve_instance_paths
from aec_bench.trials import PlannedTrial
from tests.support.task_factories import make_task_definition
from tests.support.trial_record_factories import make_trial_record


def _batch(tmp_path: Path, *, visibility: Visibility = Visibility.PUBLIC) -> CandidateEvaluationBatch:
    task_id = "electrical/voltage-drop/development"
    resolved = resolve_instance_paths(
        make_task_definition(task_id=task_id, visibility=visibility),
        tmp_path / "task",
    )
    trial = PlannedTrial(
        trial_id="development-planned-trial",
        experiment_id="development-experiment",
        task_id=task_id,
        agent=AgentConfig(name="development-agent", adapter="direct", model="test-model"),
        compute=ComputeConfig(backend="local"),
        repetition=1,
    )
    return CandidateEvaluationBatch(
        tasks=(resolved,),
        trials=(trial,),
        evaluation_case_ids=("development-case-1",),
    )


def _record(
    *,
    experiment_id: str = "development-experiment",
    trial_id: str = "development-trial-1",
    visibility: Visibility = Visibility.PUBLIC,
):
    task_id = "electrical/voltage-drop/development"
    return make_trial_record(
        experiment_id=experiment_id,
        trial_id=trial_id,
        task_id=task_id,
        task={"task_id": task_id, "task_revision": "task-revision", "visibility": visibility},
        inputs={
            "instruction": "Review the task and write findings.",
            "task_revision": "task-revision",
            "visibility": visibility,
            "system_prompt": "Use the development candidate.",
        },
    )


def test_planner_is_called_once_and_returns_one_fixed_public_batch(tmp_path: Path) -> None:
    batch = _batch(tmp_path)
    calls: list[tuple[int, int]] = []

    def planner(batch_size: int, cycle: int) -> CandidateEvaluationBatch:
        calls.append((batch_size, cycle))
        return batch

    boundary = DevelopmentEvaluationBoundary(
        planner=planner,
        evaluator=make_deterministic_development_evaluator((_record(),)),
        batch_size=1,
        cycle=2,
        experiment_id="development-experiment",
        host_experiment_id="host-experiment",
    )

    assert boundary.plan() is batch
    assert boundary.plan() is batch
    assert boundary.batch is batch
    assert calls == [(1, 2)]


def test_holdout_batch_is_rejected_before_evaluation(tmp_path: Path) -> None:
    batch = _batch(tmp_path, visibility=Visibility.HOLDOUT)
    evaluated = False

    def evaluate(_snapshot: WorkspaceSnapshot, _batch: CandidateEvaluationBatch):
        nonlocal evaluated
        evaluated = True
        return (_record(),)

    boundary = DevelopmentEvaluationBoundary(planner=lambda _size, _cycle: batch, evaluator=evaluate, batch_size=1)

    with pytest.raises(ValueError, match="only PUBLIC tasks"):
        boundary.plan()
    assert evaluated is False


def test_development_role_and_experiment_are_distinct_from_host(tmp_path: Path) -> None:
    batch = _batch(tmp_path)
    boundary = DevelopmentEvaluationBoundary(
        planner=make_deterministic_development_batch_planner(batch),
        evaluator=make_deterministic_development_evaluator((_record(),)),
        batch_size=1,
        experiment_id="development-experiment",
        host_experiment_id="host-experiment",
    )

    assert boundary.role is EvaluationRole.DEVELOPMENT
    assert EvaluationRole.DEVELOPMENT is not EvaluationRole.HOST

    host_record_boundary = DevelopmentEvaluationBoundary(
        planner=make_deterministic_development_batch_planner(batch),
        evaluator=make_deterministic_development_evaluator((_record(experiment_id="host-experiment"),)),
        batch_size=1,
        experiment_id="development-experiment",
        host_experiment_id="host-experiment",
    )
    with pytest.raises(ValueError, match="host experiment identity"):
        host_record_boundary.evaluate(WorkspaceSnapshot(system_prompt="Prompt.", candidate_id="candidate-1"))


def test_returned_record_must_use_the_planned_development_experiment(tmp_path: Path) -> None:
    batch = _batch(tmp_path)
    boundary = DevelopmentEvaluationBoundary(
        planner=make_deterministic_development_batch_planner(batch),
        evaluator=make_deterministic_development_evaluator((_record(experiment_id="different-experiment"),)),
        batch_size=1,
        experiment_id="development-experiment",
    )

    with pytest.raises(ValueError, match="match the planned development experiment identity"):
        boundary.evaluate(WorkspaceSnapshot(system_prompt="Prompt.", candidate_id="candidate-1"))


def test_returned_record_must_not_reuse_a_host_trial_identity(tmp_path: Path) -> None:
    batch = _batch(tmp_path)
    boundary = DevelopmentEvaluationBoundary(
        planner=make_deterministic_development_batch_planner(batch),
        evaluator=make_deterministic_development_evaluator((_record(trial_id="host-trial-1"),)),
        batch_size=1,
        experiment_id="development-experiment",
        host_trial_ids=("host-trial-1",),
    )

    with pytest.raises(ValueError, match="collide with a host trial identity"):
        boundary.evaluate(WorkspaceSnapshot(system_prompt="Prompt.", candidate_id="candidate-1"))


def test_revision_is_bound_to_exact_trial_evidence_and_development_provenance(tmp_path: Path) -> None:
    batch = _batch(tmp_path)
    boundary = DevelopmentEvaluationBoundary(
        planner=make_deterministic_development_batch_planner(batch),
        evaluator=make_deterministic_development_evaluator((_record(),)),
        batch_size=1,
        experiment_id="development-experiment",
        host_experiment_id="host-experiment",
    )
    snapshot = WorkspaceSnapshot(system_prompt="Candidate prompt.", candidate_id="candidate-1")

    attempt = boundary.evaluate_revision(
        snapshot,
        attempt_id="attempt-1",
        revision=1,
        mutation=MutationSummary(prompt_modified=True),
        hypothesis="Use a clearer verification step.",
        usage_after=VariationUsage(development_evaluations=1),
    )

    assert attempt.evaluated.snapshot == snapshot
    assert attempt.evaluated.assessment.evaluation_case_ids == batch.evaluation_case_ids
    provenance = attempt.evaluated.observations[0].trial.pending_extensions["development_evaluation"]
    assert provenance.role is EvaluationRole.DEVELOPMENT
    assert provenance.experiment_id == "development-experiment"
    assert provenance.trial_id == "development-trial-1"
    assert provenance.candidate_id == "candidate-1"
    assert provenance.revision == 1
    assert provenance.evaluation_case_id == "development-case-1"


def test_returned_holdout_trial_record_is_rejected(tmp_path: Path) -> None:
    batch = _batch(tmp_path)
    boundary = DevelopmentEvaluationBoundary(
        planner=make_deterministic_development_batch_planner(batch),
        evaluator=make_deterministic_development_evaluator((_record(visibility=Visibility.HOLDOUT),)),
        batch_size=1,
    )

    with pytest.raises(ValueError, match="visibility must be PUBLIC"):
        boundary.evaluate(WorkspaceSnapshot(system_prompt="Prompt.", candidate_id="candidate-1"))
