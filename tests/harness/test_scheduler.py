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
from aec_bench.contracts.identity import new_entity_id
from aec_bench.contracts.task_definition import Difficulty, Lifecycle, Visibility
from aec_bench.dataset.publication import publish_dataset
from aec_bench.dataset.storage import save_dataset
from aec_bench.harness.scheduler import (
    batch_planned_trials,
    select_manifest_tasks,
)
from aec_bench.trials import plan_trials
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
        tasks=tuple(tasks),
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


def test_plan_trials_expands_tasks_agents_and_repetitions() -> None:
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

    plan = plan_trials(
        manifest.experiment_id,
        tasks=tasks,
        agents=manifest.agents,
        compute=manifest.compute,
        repetitions=manifest.repetitions,
    )

    assert len(plan) == 8
    assert plan[0].trial_id == "experiment-001--mechanical-heat-load-alpha--agent-a--rep01"
    assert plan[-1].trial_id == "experiment-001--mechanical-heat-load-beta--agent-b--rep02"
    assert all(item.compute == manifest.compute for item in plan)


def test_plan_trials_uses_explicit_local_compute_by_default() -> None:
    tasks = [make_task_definition(task_id="mechanical/heat-load/alpha")]
    agent = AgentConfig(name="agent-a", adapter="direct", model="test-model")

    plan = plan_trials("direct-plan", tasks=tasks, agents=[agent])

    assert len(plan) == 1
    assert plan[0].compute == ComputeConfig(backend="local")


def test_batch_planned_trials_respects_max_concurrency() -> None:
    tasks = [make_task_definition(task_id=f"mechanical/heat-load/task-{idx}") for idx in range(5)]
    manifest = ExperimentManifest(
        experiment_id="experiment-001",
        name="Batching",
        tasks=TaskSelector(domains=["mechanical"]),
        agents=[AgentConfig(name="agent-a", adapter="tool_loop", model="gpt-5.4")],
        compute=ComputeConfig(backend="modal"),
    )

    plan = plan_trials(
        manifest.experiment_id,
        tasks=tasks,
        agents=manifest.agents,
        compute=manifest.compute,
        repetitions=manifest.repetitions,
    )
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
    (task_directory / "task.toml").write_text(
        "[identity]\n"
        f'id = "{new_entity_id("task")}"\n'
        'key = "electrical/voltage-drop/alpha"\n'
        "version = 1\n\n"
        '[metadata]\nlifecycle = "active"\nvisibility = "public"\n',
        encoding="utf-8",
    )
    (task_directory / "instruction.md").write_text("Complete the task.\n", encoding="utf-8")
    (task_directory / "tests").mkdir()
    (task_directory / "tests/test.sh").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    datasets_root = project_root / "datasets"
    save_dataset(datasets_root, dataset)
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


def test_select_manifest_tasks_loads_dataset_task_from_declared_path(tmp_path: Path) -> None:
    tasks = [
        make_task_definition(task_id="electrical/voltage-drop/alpha", domain="electrical"),
        make_task_definition(task_id="electrical/voltage-drop/beta", domain="electrical"),
    ]
    dataset = _make_dataset_manifest(task_ids=["electrical/voltage-drop/missing"])
    project_root = tmp_path / "project"
    task_directory = project_root / "tasks/electrical/voltage-drop/missing"
    task_directory.mkdir(parents=True)
    (task_directory / "task.toml").write_text(
        "[identity]\n"
        f'id = "{new_entity_id("task")}"\n'
        'key = "electrical/voltage-drop/missing"\n'
        "version = 1\n\n"
        '[metadata]\nlifecycle = "active"\nvisibility = "public"\n',
        encoding="utf-8",
    )
    (task_directory / "instruction.md").write_text("Complete the task.\n", encoding="utf-8")
    (task_directory / "tests").mkdir()
    (task_directory / "tests/test.sh").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    datasets_root = project_root / "datasets"
    save_dataset(datasets_root, dataset)
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

    selected = select_manifest_tasks(
        tasks,
        manifest,
        datasets_root=datasets_root,
        project_root=project_root,
    )

    assert [task.task_id for task in selected] == ["electrical/voltage-drop/missing"]


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


def test_manifest_selection_defaults_to_active_public_tasks() -> None:
    tasks = [
        make_task_definition(task_id="electrical/active", lifecycle=Lifecycle.ACTIVE),
        make_task_definition(task_id="electrical/deprecated", lifecycle=Lifecycle.DEPRECATED),
        make_task_definition(task_id="electrical/private", visibility=Visibility.PRIVATE),
        make_task_definition(task_id="electrical/holdout", visibility=Visibility.HOLDOUT),
    ]
    manifest = ExperimentManifest(
        experiment_id="experiment-001",
        name="Default policy",
        tasks=TaskSelector(),
        agents=[AgentConfig(name="agent-a", adapter="tool_loop", model="gpt-5.4")],
        compute=ComputeConfig(backend="modal"),
    )

    selected = select_manifest_tasks(tasks, manifest)

    assert [task.task_id for task in selected] == ["electrical/active"]


def test_manifest_selection_requires_explicit_deprecated_opt_in() -> None:
    task = make_task_definition(task_id="electrical/deprecated", lifecycle=Lifecycle.DEPRECATED)
    manifest = ExperimentManifest(
        experiment_id="experiment-001",
        name="Deprecated policy",
        tasks=TaskSelector(lifecycle_filter=[Lifecycle.DEPRECATED]),
        agents=[AgentConfig(name="agent-a", adapter="tool_loop", model="gpt-5.4")],
        compute=ComputeConfig(backend="modal"),
    )

    assert select_manifest_tasks([task], manifest) == [task]


@pytest.mark.parametrize("lifecycle", [Lifecycle.PROPOSED, Lifecycle.RETIRED])
def test_manifest_selection_rejects_proposed_and_retired_tasks(lifecycle: Lifecycle) -> None:
    task = make_task_definition(task_id=f"electrical/{lifecycle.value}", lifecycle=lifecycle)
    manifest = ExperimentManifest.model_construct(
        experiment_id="experiment-001",
        name="Forbidden lifecycle policy",
        tasks=TaskSelector.model_construct(
            dataset=None,
            include_patterns=[],
            exclude_patterns=[],
            domains=[],
            difficulties=[],
            lifecycle_filter=[lifecycle],
            visibility_filter=[Visibility.PUBLIC],
        ),
        agents=[AgentConfig(name="agent-a", adapter="tool_loop", model="gpt-5.4")],
        compute=ComputeConfig(backend="modal"),
        repetitions=1,
        disable_verification=False,
        description=None,
        reviewer=None,
    )

    with pytest.raises(ValueError, match=f"{lifecycle.value}.*cannot start"):
        select_manifest_tasks([task], manifest)


def test_manifest_selection_allows_non_public_tasks_only_with_explicit_context() -> None:
    task = make_task_definition(task_id="electrical/holdout", visibility=Visibility.HOLDOUT)
    manifest = ExperimentManifest(
        experiment_id="experiment-001",
        name="Holdout policy",
        tasks=TaskSelector(visibility_filter=[Visibility.HOLDOUT]),
        agents=[AgentConfig(name="agent-a", adapter="tool_loop", model="gpt-5.4")],
        compute=ComputeConfig(backend="modal"),
    )

    assert select_manifest_tasks([task], manifest) == [task]


def test_plan_trials_rejects_forbidden_lifecycle_and_visibility_without_context() -> None:
    agent = AgentConfig(name="agent-a", adapter="direct", model="test-model")

    with pytest.raises(ValueError, match="proposed.*cannot start"):
        plan_trials("forbidden", tasks=[make_task_definition(lifecycle=Lifecycle.PROPOSED)], agents=[agent])
    with pytest.raises(ValueError, match="retired.*cannot start"):
        plan_trials("forbidden", tasks=[make_task_definition(lifecycle=Lifecycle.RETIRED)], agents=[agent])
    with pytest.raises(ValueError, match="holdout.*explicit permitted"):
        plan_trials("forbidden", tasks=[make_task_definition(visibility=Visibility.HOLDOUT)], agents=[agent])


def test_plan_trials_accepts_explicit_holdout_context() -> None:
    agent = AgentConfig(name="agent-a", adapter="direct", model="test-model")
    task = make_task_definition(visibility=Visibility.HOLDOUT)

    plan = plan_trials(
        "permitted",
        tasks=[task],
        agents=[agent],
        permitted_visibility=[Visibility.HOLDOUT],
    )

    assert len(plan) == 1
