# ABOUTME: Tests candidate-independent evaluation batches and exact evidence binding.
# ABOUTME: Proves both candidates use the same planned cases and evaluation owns validity.

from pathlib import Path
from typing import Any

import pytest

from aec_bench.contracts.evaluation_result import EvaluationResult, ValidityCheck
from aec_bench.contracts.evolution import ObservationEnrichment, WorkspaceSnapshot
from aec_bench.contracts.experiment_manifest import AgentConfig, ComputeConfig
from aec_bench.contracts.trial_record import EvaluationStatus
from aec_bench.evolution.backends import local
from aec_bench.evolution.evaluation import (
    CandidateEvaluationBatch,
    bind_candidate_evaluation,
    build_candidate_assessment,
    build_observations,
    validate_comparable_candidates,
)
from aec_bench.tasks.instance import resolve_instance_paths
from aec_bench.trials import PlannedTrial
from tests.support.task_factories import make_task_definition
from tests.support.trial_record_factories import make_trial_record


def _batch(
    tmp_path: Path,
    *,
    trial_id: str = "trial-1",
    case_id: str = "case-1",
    task_id: str = "electrical/check/one",
) -> CandidateEvaluationBatch:
    task_dir = tmp_path / "task"
    task_dir.mkdir(parents=True)
    resolved = resolve_instance_paths(make_task_definition(task_id=task_id), task_dir)
    trial = PlannedTrial(
        trial_id=trial_id,
        experiment_id="evolution-cycle-0",
        task_id=task_id,
        agent=AgentConfig(name="evolution-agent", adapter="direct", model="test-model"),
        compute=ComputeConfig(backend="local"),
        repetition=1,
    )
    return CandidateEvaluationBatch(tasks=(resolved,), trials=(trial,), evaluation_case_ids=(case_id,), cycle=0)


def test_batch_cases_are_candidate_independent(tmp_path: Path) -> None:
    batch = _batch(tmp_path)
    parent_records = (make_trial_record(trial_id="trial-1", task_id="electrical/check/one"),)
    child_records = (make_trial_record(trial_id="trial-2", task_id="electrical/check/one"),)

    parent = bind_candidate_evaluation(
        WorkspaceSnapshot(system_prompt="Parent.", candidate_id="parent"),
        batch,
        parent_records,
    )
    child = bind_candidate_evaluation(
        WorkspaceSnapshot(system_prompt="Child.", candidate_id="child"),
        batch,
        child_records,
    )

    validate_comparable_candidates(parent, child)
    assert parent.assessment.evaluation_case_ids == child.assessment.evaluation_case_ids == ("case-1",)


def test_different_evaluation_cases_cannot_be_compared(tmp_path: Path) -> None:
    parent_batch = _batch(tmp_path, trial_id="trial-1", case_id="case-1")
    child_batch = _batch(tmp_path / "child", trial_id="trial-2", case_id="case-2")
    parent = bind_candidate_evaluation(
        WorkspaceSnapshot(system_prompt="Parent.", candidate_id="parent"),
        parent_batch,
        (make_trial_record(trial_id="trial-1", task_id="electrical/check/one"),),
    )
    child = bind_candidate_evaluation(
        WorkspaceSnapshot(system_prompt="Child.", candidate_id="child"),
        child_batch,
        (make_trial_record(trial_id="trial-2", task_id="electrical/check/one"),),
    )

    with pytest.raises(ValueError, match="identical evaluation_case_ids"):
        validate_comparable_candidates(parent, child)


def test_returned_record_must_match_planned_task_and_attempt(tmp_path: Path) -> None:
    batch = _batch(tmp_path)
    record = make_trial_record(trial_id="trial-1", task_id="electrical/check/different", attempt=1)

    with pytest.raises(ValueError, match="task_id must match"):
        build_observations((record,), "candidate", batch=batch)


def test_assessment_uses_trial_evaluation_and_preserves_invalidity(tmp_path: Path) -> None:
    batch = _batch(tmp_path)
    records = (make_trial_record(trial_id="trial-1", task_id="electrical/check/one", evaluation=None),)
    observations = build_observations(records, "candidate", batch=batch)

    with pytest.raises(ValueError, match="trial trial-1 has no EvaluationResult evidence"):
        build_candidate_assessment("candidate", batch, observations)


def test_non_completed_evaluation_retains_reward_and_trial_qualified_invalidity(tmp_path: Path) -> None:
    batch = _batch(tmp_path)
    record = make_trial_record(
        trial_id="trial-1",
        task_id="electrical/check/one",
        evaluation_status=EvaluationStatus.FAILED,
        evaluation=EvaluationResult(
            reward=0.73,
            validity=ValidityCheck(
                output_parseable=True,
                schema_valid=True,
                verifier_completed=True,
            ),
        ),
    )
    observations = build_observations((record,), "candidate", batch=batch)

    assessment = build_candidate_assessment("candidate", batch, observations)

    assert assessment.valid is False
    assert assessment.batch_score == pytest.approx(0.73)
    assert assessment.invalid_reasons == ("trial trial-1: evaluation status is failed",)


def test_validity_errors_are_qualified_by_trial_id(tmp_path: Path) -> None:
    batch = _batch(tmp_path)
    record = make_trial_record(
        trial_id="trial-1",
        task_id="electrical/check/one",
        evaluation=EvaluationResult(
            reward=0.0,
            validity=ValidityCheck(
                output_parseable=False,
                schema_valid=True,
                verifier_completed=True,
                errors=["parse failed"],
            ),
        ),
    )

    assessment = build_candidate_assessment(
        "candidate",
        batch,
        build_observations((record,), "candidate", batch=batch),
    )

    assert assessment.invalid_reasons == ("trial trial-1: parse failed",)


def test_enrichment_must_preserve_record_order(tmp_path: Path) -> None:
    batch = _batch(tmp_path)
    records = (make_trial_record(trial_id="trial-1", task_id="electrical/check/one"),)

    with pytest.raises(ValueError, match="enrichment count"):
        build_observations(
            records,
            "candidate",
            enrichments=(ObservationEnrichment(), ObservationEnrichment()),
            batch=batch,
        )

    observations = build_observations(
        records,
        "candidate",
        enrichments=(ObservationEnrichment(),),
        batch=batch,
    )
    assert observations[0].trial.trial_id == "trial-1"


def test_stub_evaluator_requires_exact_batch_records(tmp_path: Path) -> None:
    batch = _batch(tmp_path)
    solve = local.make_stub_candidate_evaluator([make_trial_record(trial_id="trial-1", task_id="electrical/check/one")])

    records = solve(WorkspaceSnapshot(system_prompt="Prompt.", candidate_id="candidate"), batch)

    assert records[0].trial_id == "trial-1"


def test_local_evaluator_reuses_planned_tasks_and_cases(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    batch = _batch(tmp_path)
    observed: dict[str, Any] = {}
    record = make_trial_record(trial_id="trial-1", task_id="electrical/check/one")

    def fake_run_experiment(**kwargs: Any) -> list[Any]:
        observed.update(kwargs)
        return [record]

    monkeypatch.setattr(local, "run_experiment", fake_run_experiment)
    solve = local.make_local_candidate_evaluator(workspace_root=tmp_path)

    result = solve(WorkspaceSnapshot(system_prompt="Candidate prompt.", candidate_id="candidate"), batch)

    assert result == (record,)
    assert observed["tasks"] == batch.tasks
    assert observed["trials"][0].trial_id != batch.trials[0].trial_id
    assert observed["trials"][0].experiment_id.endswith("--candidate-candidate")
    assert observed["trials"][0].agent.system_prompt is not None
    assert "Candidate prompt." in observed["trials"][0].agent.system_prompt
