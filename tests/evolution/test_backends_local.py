# ABOUTME: Tests the local evolution CandidateEvaluator composition boundary.
# ABOUTME: Proves snapshots become agent input and fitness trials use run_experiment.

from pathlib import Path
from typing import Any

from aec_bench.contracts.evolution import SkillEntry, WorkspaceSnapshot
from aec_bench.evolution.backends import local
from aec_bench.tasks.instance import resolve_instance_paths
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


def test_stub_candidate_evaluator_limits_fixed_records() -> None:
    records = [make_trial_record(trial_id="trial-1"), make_trial_record(trial_id="trial-2")]

    assert local.make_stub_candidate_evaluator(records)(_snapshot(), 1) == records[:1]


def test_local_candidate_evaluator_plans_and_runs_snapshot_as_explicit_agent_input(
    tmp_path: Path,
    monkeypatch,
) -> None:  # noqa: ANN001
    first = _resolved_task(tmp_path, "electrical/voltage-drop/one")
    second = _resolved_task(tmp_path, "electrical/voltage-drop/two")
    record = make_trial_record(trial_id="fitness-trial")
    observed: dict[str, Any] = {}
    monkeypatch.setattr(local, "_resolve_task_directories", lambda _paths: [first, second])

    def fake_run_experiment(**kwargs: Any):  # noqa: ANN202
        observed.update(kwargs)
        return [record]

    monkeypatch.setattr(local, "run_experiment", fake_run_experiment)
    solve = local.make_local_candidate_evaluator(
        task_dirs=[first.instance_dir, second.instance_dir],
        model="test-model",
        experiment_id="evolution-test",
        adapter="direct",
        timeout=25,
    )

    assert solve(_snapshot(), 1) == [record]

    assert observed["tasks"] == [first]
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
    selected: list[str] = []
    monkeypatch.setattr(local, "_resolve_task_directories", lambda _paths: [first, second])

    def fake_run_experiment(**kwargs: Any):  # noqa: ANN202
        selected.extend(task.task.task_id for task in kwargs["tasks"])
        return []

    monkeypatch.setattr(local, "run_experiment", fake_run_experiment)
    solve = local.make_local_candidate_evaluator(
        task_dirs=[first.instance_dir, second.instance_dir],
        model="test-model",
        experiment_id="evolution-test",
    )

    solve(_snapshot(), 1)
    solve(_snapshot(), 1)

    assert selected == [first.task.task_id, second.task.task_id]


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
        return []

    monkeypatch.setattr(local, "run_experiment", fake_run_experiment)
    solve = local.make_local_candidate_evaluator(
        task_dirs=[task.instance_dir],
        model="test-model",
        experiment_id="evolution-test",
        workspace_root=workspace_root,
    )

    solve(_snapshot(), 1)

    assert observed["runtime"]._agent_files == {"tool_loop.toml": config}


def test_local_candidate_evaluator_returns_empty_for_no_tasks() -> None:
    solve = local.make_local_candidate_evaluator(task_dirs=[], model="test-model", experiment_id="evolution-test")

    assert solve(_snapshot(), 5) == []
