# ABOUTME: Tests task-ecology baseline discovery and summary aggregation helpers.
# ABOUTME: Keeps the calibration runner deterministic without invoking live agents.

from __future__ import annotations

from pathlib import Path

from aec_bench.experiments.task_ecology_baseline import (
    discover_baseline_tasks,
    summarise_baseline_rows,
    validate_baseline_environment,
)


def test_discover_baseline_tasks_reads_generated_metadata(tmp_path: Path) -> None:
    task_dir = (
        tmp_path
        / "tasks"
        / "generated"
        / "task-ecology-exp1"
        / "fixed"
        / "civil"
        / "oil-containment"
        / "bund-volume-calculation"
        / "sample-00"
    )
    task_dir.mkdir(parents=True)
    (task_dir / "task.toml").write_text(
        """
version = "1.0"

[metadata]
domain = "civil"
category = "oil-containment"
difficulty = "medium"

[generation]
template = "bund-volume-calculation"
difficulty = "hard"
""",
        encoding="utf-8",
    )

    tasks = discover_baseline_tasks(
        tasks_root=tmp_path / "tasks",
        experiment="task-ecology-exp1",
        suites=("fixed",),
    )

    assert len(tasks) == 1
    assert tasks[0].task_id == (
        "generated/task-ecology-exp1/fixed/civil/oil-containment/bund-volume-calculation/sample-00"
    )
    assert tasks[0].suite == "fixed"
    assert tasks[0].domain == "civil"
    assert tasks[0].difficulty == "hard"
    assert tasks[0].template == "bund-volume-calculation"


def test_summarise_baseline_rows_groups_pressure_tasks() -> None:
    rows = [
        {
            "task_id": "fixed/easy",
            "suite": "fixed",
            "domain": "civil",
            "template": "bund-volume-calculation",
            "difficulty": "easy",
            "reward": 1.0,
        },
        {
            "task_id": "population/hard",
            "suite": "population",
            "domain": "electrical",
            "template": "dc-ac-ratio",
            "difficulty": "hard",
            "reward": 0.6,
        },
    ]

    summary = summarise_baseline_rows(rows, score_threshold=0.85)

    assert summary["total_tasks"] == 2
    assert summary["mean_reward"] == 0.8
    assert summary["below_threshold_count"] == 1
    assert summary["by_suite"]["fixed"]["mean_reward"] == 1.0
    assert summary["by_difficulty"]["hard"]["below_threshold_count"] == 1
    assert summary["below_threshold_tasks"] == [
        {
            "task_id": "population/hard",
            "reward": 0.6,
            "suite": "population",
            "difficulty": "hard",
            "template": "dc-ac-ratio",
        }
    ]


def test_validate_baseline_environment_requires_anthropic_key(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    try:
        validate_baseline_environment("claude-sonnet-4-20250514")
    except RuntimeError as exc:
        assert "ANTHROPIC_API_KEY" in str(exc)
    else:
        raise AssertionError("Expected missing Anthropic credentials to fail fast")

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    validate_baseline_environment("claude-sonnet-4-20250514")
