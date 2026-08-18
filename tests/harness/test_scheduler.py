# ABOUTME: Tests for manifest-driven trial planning and bounded batching in the harness.
# ABOUTME: Verifies deterministic expansion across tasks, agents, repetitions, and concurrency.

from pathlib import Path

import pytest

from aec_bench.contracts.dataset import (
    DatasetManifest,
    DatasetTaskEntry,
)
from aec_bench.contracts.experiment_manifest import (
    AgentConfig,
    ComputeConfig,
    ExperimentManifest,
    TaskSelector,
)
from aec_bench.contracts.task_definition import Difficulty
from aec_bench.dataset.publication import publish_dataset
from aec_bench.dataset.storage import write_manifest
from aec_bench.harness.scheduler import (
    batch_planned_trials,
    build_trial_plan,
    select_manifest_tasks,
)
from tests.support.task_factories import make_task_definition


def _make_dataset_manifest(
    name: str = "bench-suite",
    task_ids: list[str] | None = None,
) -> DatasetManifest:
    task_ids = task_ids or ["electrical/voltage-drop/instance-0"]
    tasks = [
        DatasetTaskEntry(
            task_id=tid,
            path=f"tasks/{tid}",
            task_kind="artifact",
        )
        for tid in task_ids
    ]
    return DatasetManifest(
        dataset_id=name,
        description="Test dataset",
        tasks=tasks,
    )


def test_select_manifest_tasks_filters_against_manifest_selector() -> None:
    tasks = [
        make_task_definition(
            task_id="mechanical/heat-load/alpha",
            domain="mechanical",
            difficulty=Difficulty.MEDIUM,
        ),
        make_task_definition(
            task_id="electrical/voltage-drop/beta",
            domain="electrical",
            difficulty=Difficulty.EASY,
        ),
    ]
    manifest = ExperimentManifest(
        experiment_id="experiment-001",
        name="Mechanical only",
        tasks=TaskSelector(domains=["mechanical"], difficulties=[Difficulty.MEDIUM]),
        agents=[AgentConfig(name="agent-a", adapter="tool_loop", model="gpt-5.4")],
        compute=ComputeConfig(backend="modal"),
    )

    selected = select_manifest_tasks(tasks, manifest)

    assert [task.task_id for task in selected] == ["mechanical/heat-load/alpha"]


def test_build_trial_plan_expands_tasks_agents_and_repetitions() -> None:
    tasks = [
        make_task_definition(task_id="mechanical/heat-load/alpha", domain="mechanical"),
        make_task_definition(task_id="mechanical/heat-load/beta", domain="mechanical"),
    ]
    manifest = ExperimentManifest(
        experiment_id="experiment-001",
        name="Two agents, two reps",
        tasks=TaskSelector(domains=["mechanical"]),
        agents=[
            AgentConfig(name="agent-a", adapter="tool_loop", model="gpt-5.4"),
            AgentConfig(name="agent-b", adapter="direct", model="gpt-5.4-mini"),
        ],
        compute=ComputeConfig(backend="modal"),
        repetitions=2,
    )

    plan = build_trial_plan(manifest, tasks)

    assert len(plan) == 8
    assert plan[0].trial_id == "experiment-001--mechanical-heat-load-alpha--agent-a--rep01"
    assert plan[-1].trial_id == "experiment-001--mechanical-heat-load-beta--agent-b--rep02"
    assert all(item.compute_backend == "modal" for item in plan)


def test_batch_planned_trials_respects_max_concurrency() -> None:
    tasks = [make_task_definition(task_id=f"mechanical/heat-load/task-{idx}") for idx in range(5)]
    manifest = ExperimentManifest(
        experiment_id="experiment-001",
        name="Batching",
        tasks=TaskSelector(domains=["mechanical"]),
        agents=[AgentConfig(name="agent-a", adapter="tool_loop", model="gpt-5.4")],
        compute=ComputeConfig(backend="modal"),
    )

    plan = build_trial_plan(manifest, tasks)
    batches = batch_planned_trials(plan, max_concurrency=2)

    assert [len(batch) for batch in batches] == [2, 2, 1]


def test_select_manifest_tasks_filters_by_dataset_when_set(tmp_path: Path) -> None:
    tasks = [
        make_task_definition(task_id="electrical/voltage-drop/alpha", domain="electrical"),
        make_task_definition(task_id="electrical/voltage-drop/beta", domain="electrical"),
        make_task_definition(task_id="mechanical/heat-load/gamma", domain="mechanical"),
    ]
    dataset = _make_dataset_manifest(
        name="bench-suite",
        task_ids=["electrical/voltage-drop/alpha"],
    )
    project_root = tmp_path / "project"
    task_directory = project_root / "tasks/electrical/voltage-drop/alpha"
    task_directory.mkdir(parents=True)
    (task_directory / "task.toml").write_text("[metadata]\n", encoding="utf-8")
    datasets_root = project_root / "datasets"
    write_manifest(datasets_root, dataset)
    publication = publish_dataset(
        manifest=dataset,
        datasets_root=datasets_root,
        project_root=project_root,
        label="public-2026",
    )
    manifest = ExperimentManifest(
        experiment_id="experiment-001",
        name="Dataset filtered run",
        tasks=TaskSelector(dataset=publication.dataset_ref),
        agents=[AgentConfig(name="agent-a", adapter="tool_loop", model="gpt-5.4")],
        compute=ComputeConfig(backend="modal"),
    )

    selected = select_manifest_tasks(
        tasks,
        manifest,
        datasets_root=datasets_root,
        project_root=project_root,
    )

    assert [task.task_id for task in selected] == ["electrical/voltage-drop/alpha"]


def test_select_manifest_tasks_rejects_missing_registered_task(tmp_path: Path) -> None:
    tasks = [
        make_task_definition(task_id="electrical/voltage-drop/alpha", domain="electrical"),
        make_task_definition(task_id="electrical/voltage-drop/beta", domain="electrical"),
    ]
    dataset = _make_dataset_manifest(task_ids=["electrical/voltage-drop/missing"])
    project_root = tmp_path / "project"
    task_directory = project_root / "tasks/electrical/voltage-drop/missing"
    task_directory.mkdir(parents=True)
    (task_directory / "task.toml").write_text("[metadata]\n", encoding="utf-8")
    datasets_root = project_root / "datasets"
    write_manifest(datasets_root, dataset)
    publication = publish_dataset(
        manifest=dataset,
        datasets_root=datasets_root,
        project_root=project_root,
        label="public-2026",
    )
    manifest = ExperimentManifest(
        experiment_id="experiment-001",
        name="Missing task rejection",
        tasks=TaskSelector(dataset=publication.dataset_ref),
        agents=[AgentConfig(name="agent-a", adapter="tool_loop", model="gpt-5.4")],
        compute=ComputeConfig(backend="modal"),
    )

    with pytest.raises(ValueError, match="not registered"):
        select_manifest_tasks(
            tasks,
            manifest,
            datasets_root=datasets_root,
            project_root=project_root,
        )


def test_select_manifest_tasks_without_dataset_field_is_unchanged() -> None:
    tasks = [
        make_task_definition(task_id="electrical/voltage-drop/alpha", domain="electrical"),
    ]
    manifest = ExperimentManifest(
        experiment_id="experiment-001",
        name="No dataset field",
        tasks=TaskSelector(),
        agents=[AgentConfig(name="agent-a", adapter="tool_loop", model="gpt-5.4")],
        compute=ComputeConfig(backend="modal"),
    )

    selected = select_manifest_tasks(tasks, manifest)

    assert [task.task_id for task in selected] == ["electrical/voltage-drop/alpha"]
