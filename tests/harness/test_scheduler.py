# ABOUTME: Tests for manifest-driven trial planning and bounded batching in the harness.
# ABOUTME: Verifies deterministic expansion across tasks, agents, repetitions, and concurrency.

from datetime import UTC, datetime
from pathlib import Path

from aec_bench.contracts.dataset import (
    DatasetDescription,
    DatasetManifest,
    DatasetSource,
    DatasetTaskEntry,
)
from aec_bench.contracts.experiment_manifest import (
    AgentConfig,
    ComputeConfig,
    ExperimentManifest,
    TaskSelector,
)
from aec_bench.contracts.task_definition import Difficulty
from aec_bench.dataset.storage import write_manifest
from aec_bench.harness.scheduler import (
    batch_planned_trials,
    build_trial_plan,
    select_manifest_tasks,
)
from tests.support.task_factories import make_task_definition


def _make_dataset_manifest(
    name: str = "bench-suite",
    version: str = "1.0.0",
    task_ids: list[str] | None = None,
) -> DatasetManifest:
    task_ids = task_ids or ["electrical/voltage-drop/instance-0"]
    tasks = [
        DatasetTaskEntry(
            task_id=tid,
            task_path=tid,
            content_hash=f"sha256-{'a' * 64}",
            domain=tid.split("/")[0],
            difficulty="medium",
        )
        for tid in task_ids
    ]
    return DatasetManifest(
        name=name,
        version=version,
        content_hash="abc123" * 10 + "abcd",
        description=DatasetDescription(
            summary="Test dataset",
            domains=[t.split("/")[0] for t in task_ids],
            task_count=len(tasks),
        ),
        created_at=datetime(2025, 6, 1, tzinfo=UTC),
        tasks=tasks,
        source=DatasetSource(method="manual"),
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
        version="1.0.0",
        task_ids=["electrical/voltage-drop/alpha"],
    )
    write_manifest(tmp_path, dataset)
    manifest = ExperimentManifest(
        experiment_id="experiment-001",
        name="Dataset filtered run",
        tasks=TaskSelector(dataset="bench-suite@1.0.0"),
        agents=[AgentConfig(name="agent-a", adapter="tool_loop", model="gpt-5.4")],
        compute=ComputeConfig(backend="modal"),
    )

    selected = select_manifest_tasks(tasks, manifest, datasets_root=tmp_path)

    assert [task.task_id for task in selected] == ["electrical/voltage-drop/alpha"]


def test_select_manifest_tasks_dataset_unresolved_keeps_all_tasks(tmp_path: Path) -> None:
    tasks = [
        make_task_definition(task_id="electrical/voltage-drop/alpha", domain="electrical"),
        make_task_definition(task_id="electrical/voltage-drop/beta", domain="electrical"),
    ]
    manifest = ExperimentManifest(
        experiment_id="experiment-001",
        name="Missing dataset fallback",
        tasks=TaskSelector(dataset="no-such-dataset@9.9.9"),
        agents=[AgentConfig(name="agent-a", adapter="tool_loop", model="gpt-5.4")],
        compute=ComputeConfig(backend="modal"),
    )

    selected = select_manifest_tasks(tasks, manifest, datasets_root=tmp_path)

    assert len(selected) == 2


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
