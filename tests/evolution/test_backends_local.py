# ABOUTME: Tests the local evolution CandidateEvaluator composition boundary.
# ABOUTME: Proves snapshots become agent input and fitness trials use run_experiment.

from pathlib import Path
from typing import Any

import pytest

from aec_bench.contracts.evolution import SkillEntry, WorkspaceSnapshot
from aec_bench.contracts.experiment_manifest import AgentConfig, ComputeConfig
from aec_bench.evolution.backends import local
from aec_bench.evolution.evaluation import CandidateEvaluationBatch
from aec_bench.tasks.instance import resolve_instance_paths
from aec_bench.trials import PlannedTrial
from tests.support.task_factories import make_task_definition
from tests.support.trial_record_factories import make_trial_record


def _snapshot(prompt: str = "Use the evolved method.") -> WorkspaceSnapshot:
    return WorkspaceSnapshot(
        system_prompt=prompt,
        skills=[
            SkillEntry(
                name="voltage-check",
                description="Check voltage drop.",
                discipline="electrical",
                body="Use the declared design current.",
            )
        ],
        candidate_id="candidate-1",
    )


def _resolved_task(tmp_path: Path, task_id: str):  # noqa: ANN202
    task_dir = tmp_path / task_id.replace("/", "-")
    task_dir.mkdir()
    return resolve_instance_paths(make_task_definition(task_id=task_id), task_dir)


def test_stub_candidate_evaluator_returns_fixed_records(tmp_path: Path) -> None:
    records = [make_trial_record(trial_id="trial-1", attempt=1), make_trial_record(trial_id="trial-2", attempt=2)]
    first = _resolved_task(tmp_path, "electrical/voltage-drop/au-office-fitout")
    first_agent = AgentConfig(name="evolution-agent", adapter="direct", model="test-model")
    first_compute = ComputeConfig(backend="local")
    batch = CandidateEvaluationBatch(
        tasks=(first,),
        trials=tuple(
            PlannedTrial(
                trial_id=record.trial_id,
                experiment_id="evolution-test",
                task_id=first.task.task_id,
                agent=first_agent,
                compute=first_compute,
                repetition=index,
            )
            for index, record in enumerate(records, start=1)
        ),
        evaluation_case_ids=("case-1", "case-2"),
    )

    assert local.make_stub_candidate_evaluator(records)(_snapshot(), batch) == tuple(records)


def test_local_candidate_evaluator_plans_and_runs_snapshot_as_explicit_agent_input(
    tmp_path: Path,
    monkeypatch,
) -> None:  # noqa: ANN001
    first = _resolved_task(tmp_path, "electrical/voltage-drop/one")
    second = _resolved_task(tmp_path, "electrical/voltage-drop/two")
    record = make_trial_record(trial_id="fitness-trial")
    observed: dict[str, Any] = {}
    monkeypatch.setattr(local, "_resolve_task_directories", lambda _paths: [first, second])

    planner = local.make_local_candidate_batch_planner(
        task_dirs=[first.instance_dir, second.instance_dir],
        model="test-model",
        experiment_id="evolution-test",
        adapter="direct",
        timeout=25,
    )
    batch = planner(1, 0)
    solve = local.make_local_candidate_evaluator()

    record = record.model_copy(update={"trial_id": batch.evaluation_case_ids[0], "task_id": batch.trials[0].task_id})

    def fake_run_experiment(**kwargs: Any):  # noqa: ANN202
        observed.update(kwargs)
        return [record]

    monkeypatch.setattr(local, "run_experiment", fake_run_experiment)
    assert solve(_snapshot(), batch) == (record,)

    assert observed["tasks"] == batch.tasks
    trial = observed["trials"][0]
    assert trial.task_id == first.task.task_id
    assert trial.compute.backend == "local"
    assert trial.compute.timeout_override == 25
    assert trial.agent.adapter == "direct"
    assert trial.agent.model == "test-model"
    assert "Use the evolved method." in trial.agent.system_prompt
    assert "voltage-check" in trial.agent.system_prompt


def test_local_candidate_evaluator_rotates_task_batches(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    first = _resolved_task(tmp_path, "electrical/voltage-drop/one")
    second = _resolved_task(tmp_path, "electrical/voltage-drop/two")
    monkeypatch.setattr(local, "_resolve_task_directories", lambda _paths: [first, second])
    planner = local.make_local_candidate_batch_planner(
        task_dirs=[first.instance_dir, second.instance_dir],
        model="test-model",
        experiment_id="evolution-test",
    )

    first_batch = planner(1, 0)
    second_batch = planner(1, 1)

    assert [first_batch.tasks[0].task.task_id, second_batch.tasks[0].task.task_id] == [
        first.task.task_id,
        second.task.task_id,
    ]


def test_local_candidate_evaluator_uses_workspace_agent_config_file(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    task = _resolved_task(tmp_path, "electrical/voltage-drop/one")
    workspace_root = tmp_path / "evolution-workspace"
    workspace_root.mkdir()
    config = workspace_root / "tool_loop.toml"
    config.write_text("[advisor]\nmax_uses = 2\n", encoding="utf-8")
    observed: dict[str, Any] = {}
    monkeypatch.setattr(local, "_resolve_task_directories", lambda _paths: [task])

    def fake_run_experiment(**kwargs: Any):  # noqa: ANN202
        observed.update(kwargs)
        return [
            make_trial_record(
                trial_id=kwargs["trials"][0].trial_id,
                task_id=kwargs["trials"][0].task_id,
            )
        ]

    monkeypatch.setattr(local, "run_experiment", fake_run_experiment)
    planner = local.make_local_candidate_batch_planner(
        task_dirs=[task.instance_dir],
        model="test-model",
        experiment_id="evolution-test",
    )
    batch = planner(1, 0)
    solve = local.make_local_candidate_evaluator(workspace_root=workspace_root)
    solve(_snapshot(), batch)

    assert observed["runtime"]._agent_files == {"tool_loop.toml": config}


def test_local_candidate_evaluator_returns_empty_for_no_tasks() -> None:
    planner = local.make_local_candidate_batch_planner(task_dirs=[], model="test-model", experiment_id="evolution-test")

    with pytest.raises(ValueError, match="requires at least one"):
        planner(5, 0)
