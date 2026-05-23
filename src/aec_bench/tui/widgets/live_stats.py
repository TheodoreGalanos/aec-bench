# ABOUTME: Pure functions for computing live statistics displayed on the TUI landing page.
# ABOUTME: Aggregates experiment, discipline, and dataset summaries from ledger and task data.

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from aec_bench.dataset.storage import list_datasets
from aec_bench.generation.discovery import scan_seeds, scan_templates
from aec_bench.ledger.reader import read_trial_records


@dataclass(frozen=True)
class ExperimentSummary:
    """Aggregate stats for a single experiment."""

    experiment_id: str
    trial_count: int
    mean_reward: float


@dataclass(frozen=True)
class DisciplineSummary:
    """Seed and template counts for a discipline."""

    discipline: str
    seed_count: int
    template_count: int


@dataclass(frozen=True)
class DatasetSummaryItem:
    """Basic identity and size for a dataset."""

    name: str
    version: str
    task_count: int


def build_experiments_summary(
    ledger_root: Path,
    experiment_id: str | None = None,
) -> list[ExperimentSummary]:
    """Build per-experiment trial count and mean reward from the ledger."""
    records = read_trial_records(ledger_root, experiment_id=experiment_id)
    if not records:
        return []

    by_exp: dict[str, list[float]] = {}
    for record in records:
        by_exp.setdefault(record.experiment_id, []).append(record.evaluation.reward)

    return sorted(
        [
            ExperimentSummary(
                experiment_id=exp_id,
                trial_count=len(rewards),
                mean_reward=sum(rewards) / len(rewards),
            )
            for exp_id, rewards in by_exp.items()
        ],
        key=lambda s: s.experiment_id,
    )


def build_disciplines_summary(
    tasks_root: Path,
    templates_root: Path,
) -> list[DisciplineSummary]:
    """Count seeds and templates per discipline."""
    seeds = scan_seeds(tasks_root)
    templates = scan_templates(templates_root)

    seed_counts: dict[str, int] = {}
    for seed in seeds:
        seed_counts[seed.discipline] = seed_counts.get(seed.discipline, 0) + 1

    template_counts: dict[str, int] = {}
    for tpl in templates:
        template_counts[tpl.discipline] = template_counts.get(tpl.discipline, 0) + 1

    all_disciplines = sorted(set(seed_counts) | set(template_counts))
    return [
        DisciplineSummary(
            discipline=disc,
            seed_count=seed_counts.get(disc, 0),
            template_count=template_counts.get(disc, 0),
        )
        for disc in all_disciplines
    ]


def build_datasets_summary(
    datasets_root: Path | None,
) -> list[DatasetSummaryItem]:
    """List datasets with name, version, and task count."""
    if datasets_root is None:
        return []

    manifests = list_datasets(datasets_root)
    return [
        DatasetSummaryItem(
            name=m.name,
            version=m.version,
            task_count=len(m.tasks),
        )
        for m in manifests
    ]
