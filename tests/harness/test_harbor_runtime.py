# ABOUTME: Tests recorded Harbor experiment composition through run_experiment.
# ABOUTME: Proves baseline record parity and rejection of unsupported attempt recipes.

from pathlib import Path
from types import SimpleNamespace

import pytest

from aec_bench.contracts.experiment_manifest import AgentConfig, ComputeConfig, ExperimentManifest, TaskSelector
from aec_bench.harness.artifact_tasks import BestOfSpec, SingleAttemptSpec, run_experiment
from aec_bench.harness.harbor_runtime import HarborExperimentRuntime
from aec_bench.ledger.writer import write_trial_record
from aec_bench.tasks.instance import resolve_instance_paths
from aec_bench.trials import plan_trials
from tests.support.task_factories import make_task_definition
from tests.support.trial_record_factories import make_trial_record


class _RecordedWorkflow:
    def __init__(self, ledger_root: Path, record_path: Path) -> None:
        self.ledger_root = ledger_root
        self._record_path = record_path
        self.calls: list[dict[str, object]] = []

    def run(self, **kwargs):  # noqa: ANN003, ANN202
        self.calls.append(kwargs)
        return SimpleNamespace(
            job_dir=self.ledger_root.parent / "recorded-job",
            import_result=SimpleNamespace(
                ledger_paths=[self._record_path],
                duplicate_trials=0,
            ),
        )


def _inputs(tmp_path: Path):  # noqa: ANN202
    task = make_task_definition(task_id="mechanical/heat-load/recorded")
    task_dir = tmp_path / "tasks" / task.task_id
    task_dir.mkdir(parents=True)
    resolved = resolve_instance_paths(task, task_dir)
    manifest = ExperimentManifest(
        experiment_id="recorded-harbor",
        name="Recorded Harbor baseline",
        tasks=TaskSelector(include_patterns=[task.task_id]),
        agents=[AgentConfig(name="agent", adapter="direct", model="test-model")],
        compute=ComputeConfig(backend="docker"),
    )
    trials = plan_trials(
        manifest.experiment_id,
        tasks=[task],
        agents=manifest.agents,
        compute=manifest.compute,
        repetitions=manifest.repetitions,
    )
    ledger_root = tmp_path / "ledger"
    expected = make_trial_record(
        trial_id=trials[0].trial_id,
        experiment_id=manifest.experiment_id,
        task_id=task.task_id,
    )
    record_path = write_trial_record(ledger_root=ledger_root, record=expected)
    workflow = _RecordedWorkflow(ledger_root, record_path)
    runtime = HarborExperimentRuntime(
        workflow=workflow,  # type: ignore[arg-type]
        manifest=manifest,
        config_path=tmp_path / "harbor.yaml",
    )
    return resolved, trials, expected, workflow, runtime


def test_recorded_harbor_baseline_returns_exact_imported_trial_meaning(tmp_path: Path) -> None:
    task, trials, expected, workflow, runtime = _inputs(tmp_path)

    records = run_experiment(
        runtime=runtime,
        tasks=[task],
        trials=trials,
        recipe=SingleAttemptSpec(),
    )

    assert [record.model_dump(mode="json") for record in records] == [expected.model_dump(mode="json")]
    assert records[0].execution_status == expected.execution_status
    assert records[0].evaluation == expected.evaluation
    assert workflow.calls[0]["resolved_tasks"] == (task.task,)
    assert workflow.calls[0]["task_path_overrides"] == {task.task.task_id: task.instance_dir.resolve()}


def test_harbor_rejects_unsupported_best_of_before_dispatch(tmp_path: Path) -> None:
    task, trials, _expected, workflow, runtime = _inputs(tmp_path)

    with pytest.raises(ValueError, match="does not support attempt recipe: best_of"):
        run_experiment(
            runtime=runtime,
            tasks=[task],
            trials=trials,
            recipe=BestOfSpec(candidates=2),
        )

    assert workflow.calls == []


def test_imported_runtime_requires_serializable_recipe_spec(tmp_path: Path) -> None:
    task, trials, _expected, _workflow, runtime = _inputs(tmp_path)

    with pytest.raises(TypeError, match="AttemptRecipeSpec"):
        run_experiment(
            runtime=runtime,
            tasks=[task],
            trials=trials,
            recipe=lambda _run_once: None,  # type: ignore[arg-type,return-value]
        )
