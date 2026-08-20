# ABOUTME: Tests for the live statistics computation functions used in the landing page.
# ABOUTME: Validates experiment, discipline, and dataset summary aggregation.

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.support.trial_record_factories import make_trial_record

# ---------------------------------------------------------------------------
# Experiment summary tests
# ---------------------------------------------------------------------------


def test_build_experiments_summary_groups_by_experiment(tmp_path: Path) -> None:
    """Records from two experiments produce two summaries with correct stats."""
    from aec_bench.tui.widgets.live_stats import build_experiments_summary

    ledger = tmp_path / "ledger"
    _write_trial(ledger, "exp-a", "t1", reward=0.8)
    _write_trial(ledger, "exp-a", "t2", reward=1.0)
    _write_trial(ledger, "exp-b", "t3", reward=0.5)

    result = build_experiments_summary(ledger)

    assert len(result) == 2
    by_exp = {s.experiment_id: s for s in result}
    assert by_exp["exp-a"].trial_count == 2
    assert by_exp["exp-a"].mean_reward == pytest.approx(0.9)
    assert by_exp["exp-b"].trial_count == 1
    assert by_exp["exp-b"].mean_reward == pytest.approx(0.5)


def test_build_experiments_summary_empty_ledger(tmp_path: Path) -> None:
    """Empty ledger returns empty list without error."""
    from aec_bench.tui.widgets.live_stats import build_experiments_summary

    ledger = tmp_path / "ledger"
    ledger.mkdir()
    result = build_experiments_summary(ledger)
    assert result == []


def test_build_experiments_summary_nonexistent_dir(tmp_path: Path) -> None:
    """Non-existent directory returns empty list."""
    from aec_bench.tui.widgets.live_stats import build_experiments_summary

    result = build_experiments_summary(tmp_path / "nope")
    assert result == []


def test_build_experiments_summary_filters_by_experiment_id(tmp_path: Path) -> None:
    """When experiment_id is provided, only that experiment is returned."""
    from aec_bench.tui.widgets.live_stats import build_experiments_summary

    ledger = tmp_path / "ledger"
    _write_trial(ledger, "exp-a", "t1", reward=0.8)
    _write_trial(ledger, "exp-b", "t2", reward=0.5)

    result = build_experiments_summary(ledger, experiment_id="exp-a")
    assert len(result) == 1
    assert result[0].experiment_id == "exp-a"


# ---------------------------------------------------------------------------
# Discipline summary tests
# ---------------------------------------------------------------------------


def test_build_disciplines_summary_counts_seeds_and_templates(tmp_path: Path) -> None:
    """Disciplines show correct seed and template counts."""
    from aec_bench.tui.widgets.live_stats import build_disciplines_summary

    tasks_root = tmp_path / "tasks"
    templates_root = tmp_path / "templates"

    _write_seed(tasks_root, "electrical", "cable-sizing")
    _write_seed(tasks_root, "electrical", "voltage-drop")
    _write_seed(tasks_root, "civil", "drainage")
    _write_template(templates_root, "electrical", "cable-sizing")

    result = build_disciplines_summary(tasks_root, templates_root)

    by_disc = {d.discipline: d for d in result}
    assert by_disc["electrical"].seed_count == 2
    assert by_disc["electrical"].template_count == 1
    assert by_disc["civil"].seed_count == 1
    assert by_disc["civil"].template_count == 0


def test_build_disciplines_summary_empty(tmp_path: Path) -> None:
    """No seeds or templates returns empty list."""
    from aec_bench.tui.widgets.live_stats import build_disciplines_summary

    result = build_disciplines_summary(tmp_path / "nope", tmp_path / "also-nope")
    assert result == []


# ---------------------------------------------------------------------------
# Dataset summary tests
# ---------------------------------------------------------------------------


def test_build_datasets_summary_lists_datasets(tmp_path: Path) -> None:
    """Datasets are returned with stable ID and task count."""
    from aec_bench.tui.widgets.live_stats import build_datasets_summary

    _write_dataset_manifest(tmp_path, "my-suite", "1.0.0", task_count=10)
    _write_dataset_manifest(tmp_path, "other-suite", "2.0.0", task_count=25)

    result = build_datasets_summary(tmp_path)

    assert len(result) == 2
    by_name = {dataset.dataset_id: dataset for dataset in result}
    assert by_name["my-suite"].task_count == 10
    assert by_name["other-suite"].task_count == 25


def test_build_datasets_summary_none_root() -> None:
    """None datasets_root returns empty list."""
    from aec_bench.tui.widgets.live_stats import build_datasets_summary

    result = build_datasets_summary(None)
    assert result == []


def test_build_datasets_summary_empty_dir(tmp_path: Path) -> None:
    """Empty directory returns empty list."""
    from aec_bench.tui.widgets.live_stats import build_datasets_summary

    result = build_datasets_summary(tmp_path)
    assert result == []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_trial(ledger: Path, experiment_id: str, trial_id: str, *, reward: float) -> None:
    """Write a trial record JSON file into the ledger directory structure."""
    record = make_trial_record(
        trial_id=trial_id,
        experiment_id=experiment_id,
        evaluation={
            "reward": reward,
            "validity": {
                "output_parseable": True,
                "schema_valid": True,
                "verifier_completed": True,
            },
        },
    )
    trial_dir = ledger / experiment_id / trial_id
    trial_dir.mkdir(parents=True, exist_ok=True)
    (trial_dir / "trial_record.json").write_text(record.model_dump_json(indent=2), encoding="utf-8")


def _write_seed(tasks_root: Path, discipline: str, task_id: str) -> None:
    """Write a minimal source_task.json seed file."""
    seed_dir = tasks_root / discipline / task_id
    seed_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "status": "proposed",
        "seed_origin": "test",
        "source": {
            "discipline": discipline,
            "task_id": task_id,
            "task_name": task_id.replace("-", " ").title(),
            "category_id": "general",
            "description": f"Test seed for {task_id}",
            "complexity": "medium",
            "standards": [],
            "inputs": [],
            "outputs": [],
        },
    }
    (seed_dir / "source_task.json").write_text(json.dumps(data), encoding="utf-8")


def _write_template(templates_root: Path, discipline: str, task_id: str) -> None:
    """Write a minimal valid template directory."""
    tpl_dir = templates_root / discipline / task_id
    tpl_dir.mkdir(parents=True, exist_ok=True)
    (tpl_dir / "params.toml").write_text(
        (
            f'[meta]\nname = "{task_id}"\ndescription = "Test"\n'
            f'discipline = "{discipline}"\ncategory = "general"\n'
            'tool_mode = "no-tool"\n'
        ),
        encoding="utf-8",
    )
    (tpl_dir / "engine.py").write_text("def compute() -> dict[str, float]:\n    return {}\n", encoding="utf-8")
    (tpl_dir / "instruction.md").write_text("Test instruction.\n", encoding="utf-8")


def _write_dataset_manifest(datasets_root: Path, name: str, version: str, *, task_count: int) -> None:
    """Write a minimal schema-2 dataset manifest."""

    from aec_bench.contracts.dataset import DatasetManifest, DatasetTaskEntry
    from aec_bench.dataset.storage import save_dataset

    del version
    save_dataset(
        datasets_root,
        DatasetManifest(
            dataset_id=name,
            description=f"Test dataset {name}",
            tasks=[
                DatasetTaskEntry(task_id=f"task-{index}", path=f"tasks/test/task-{index}", task_kind="artifact")
                for index in range(task_count)
            ],
        ),
    )
