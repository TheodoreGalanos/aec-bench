# ABOUTME: Dataset-focused leaderboard routes with single-dataset and cross-dataset scorecard views.
# ABOUTME: Aggregates trial records per model within each dataset for ranked comparison.

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, Depends, Request

from aec_bench.communication.standalone import (
    build_internal_leaderboard_artifact,
    build_public_leaderboard_artifact,
)
from aec_bench.contracts.dataset import DatasetManifest
from aec_bench.dataset.storage import list_datasets, resolve_dataset
from aec_bench.ledger.reader import query_trial_records
from aec_bench.web.dependencies import get_web_settings, require_internal_access
from aec_bench.web.schemas import (
    DatasetSummarySchema,
    LeaderboardResponse,
    ModelRowSchema,
    ScorecardCellSchema,
    ScorecardRowSchema,
)

router = APIRouter()


@dataclass(frozen=True)
class ModelRow:
    """One row in the single-dataset leaderboard table."""

    adapter: str
    model: str
    trials: int
    mean_reward: float
    perfect_pct: float
    zero_pct: float
    cost: float | None


@dataclass(frozen=True)
class ScorecardCell:
    """One cell in the cross-dataset scorecard grid."""

    mean_reward: float | None
    trials: int


@dataclass(frozen=True)
class ScorecardRow:
    """One model row in the scorecard with per-dataset scores."""

    adapter: str
    model: str
    cells: dict[str, ScorecardCell]
    overall: float | None


def _build_model_rows(
    settings_ledger_root: Any,
    dataset_id: str,
) -> list[ModelRow]:
    """Aggregate trial records into ranked model rows for a single dataset."""
    records = query_trial_records(settings_ledger_root, dataset_id=dataset_id)

    # Group by (adapter, model)
    groups: dict[tuple[str, str], list[float]] = {}
    cost_groups: dict[tuple[str, str], list[float]] = {}
    for record in records:
        key = (record.agent.adapter, record.agent.model)
        groups.setdefault(key, []).append(record.evaluation.reward)
        if record.cost and record.cost.estimated_cost_usd is not None:
            cost_groups.setdefault(key, []).append(record.cost.estimated_cost_usd)

    rows: list[ModelRow] = []
    for (adapter, model), rewards in groups.items():
        n = len(rewards)
        mean_r = sum(rewards) / n if n else 0.0
        perfect = sum(1 for r in rewards if r == 1.0) / n * 100 if n else 0.0
        zero = sum(1 for r in rewards if r == 0.0) / n * 100 if n else 0.0
        costs = cost_groups.get((adapter, model), [])
        total_cost = sum(costs) if costs else None
        rows.append(
            ModelRow(
                adapter=adapter,
                model=model,
                trials=n,
                mean_reward=round(mean_r, 4),
                perfect_pct=round(perfect, 1),
                zero_pct=round(zero, 1),
                cost=round(total_cost, 4) if total_cost is not None else None,
            )
        )

    # Sort by mean reward descending
    rows.sort(key=lambda r: r.mean_reward, reverse=True)
    return rows


def _build_scorecard(
    settings_ledger_root: Any,
    manifests: list[DatasetManifest],
) -> list[ScorecardRow]:
    """Build a cross-dataset scorecard: rows = models, columns = datasets."""
    # Collect per-dataset, per-model aggregations
    dataset_model_rewards: dict[str, dict[tuple[str, str], list[float]]] = {}
    for manifest in manifests:
        ds_id = f"{manifest.name}@{manifest.version}"
        records = query_trial_records(settings_ledger_root, dataset_id=ds_id)
        groups: dict[tuple[str, str], list[float]] = {}
        for record in records:
            key = (record.agent.adapter, record.agent.model)
            groups.setdefault(key, []).append(record.evaluation.reward)
        dataset_model_rewards[ds_id] = groups

    # Collect all model keys
    all_models: set[tuple[str, str]] = set()
    for groups in dataset_model_rewards.values():
        all_models.update(groups.keys())

    rows: list[ScorecardRow] = []
    for adapter, model in sorted(all_models):
        cells: dict[str, ScorecardCell] = {}
        all_means: list[float] = []
        for manifest in manifests:
            ds_id = f"{manifest.name}@{manifest.version}"
            rewards = dataset_model_rewards.get(ds_id, {}).get((adapter, model), [])
            if rewards:
                mean_r = sum(rewards) / len(rewards)
                cells[ds_id] = ScorecardCell(mean_reward=round(mean_r, 4), trials=len(rewards))
                all_means.append(mean_r)
            else:
                cells[ds_id] = ScorecardCell(mean_reward=None, trials=0)

        overall = round(sum(all_means) / len(all_means), 4) if all_means else None
        rows.append(ScorecardRow(adapter=adapter, model=model, cells=cells, overall=overall))

    # Sort by overall descending (None sorts last)
    rows.sort(key=lambda r: r.overall if r.overall is not None else -1.0, reverse=True)
    return rows


def _reward_class(value: float | None) -> str:
    """Return the CSS class name for a reward value."""
    if value is None:
        return ""
    if value == 1.0:
        return "reward-perfect"
    if value >= 0.7:
        return "reward-good"
    if value >= 0.4:
        return "reward-mid"
    if value > 0:
        return "reward-poor"
    return "reward-zero"


@router.get("/api/leaderboard")
def leaderboard_api(
    request: Request,
    dataset: str | None = None,
    view: str | None = None,
) -> LeaderboardResponse:
    """Return leaderboard model rows and scorecard data as JSON."""
    settings = get_web_settings(request)

    manifests = list_datasets(settings.datasets_root)
    is_scorecard = view == "scorecard"

    selected_manifest: DatasetManifest | None = None
    model_rows: list[ModelRow] = []

    if not is_scorecard:
        if dataset:
            selected_manifest = resolve_dataset(settings.datasets_root, dataset)
        if selected_manifest is None and manifests:
            selected_manifest = manifests[0]

        if selected_manifest is not None:
            ds_id = f"{selected_manifest.name}@{selected_manifest.version}"
            model_rows = _build_model_rows(settings.ledger_root, ds_id)

    scorecard_rows: list[ScorecardRow] = []
    if is_scorecard:
        scorecard_rows = _build_scorecard(settings.ledger_root, manifests)

    datasets_schema = [
        DatasetSummarySchema(
            name=m.name,
            version=m.version,
            summary=m.description.summary,
            task_count=len(m.tasks),
            domains=m.description.domains,
        )
        for m in manifests
    ]

    model_rows_schema = [
        ModelRowSchema(
            adapter=r.adapter,
            model=r.model,
            trials=r.trials,
            mean_reward=r.mean_reward,
            perfect_pct=r.perfect_pct,
            zero_pct=r.zero_pct,
            cost=r.cost,
        )
        for r in model_rows
    ]

    scorecard_rows_schema = [
        ScorecardRowSchema(
            adapter=r.adapter,
            model=r.model,
            cells={
                ds_id: ScorecardCellSchema(
                    mean_reward=cell.mean_reward,
                    trials=cell.trials,
                )
                for ds_id, cell in r.cells.items()
            },
            overall=r.overall,
        )
        for r in scorecard_rows
    ]

    selected_dataset = (
        f"{selected_manifest.name}@{selected_manifest.version}" if selected_manifest is not None else None
    )

    return LeaderboardResponse(
        model_rows=model_rows_schema,
        is_scorecard=is_scorecard,
        scorecard_rows=scorecard_rows_schema,
        datasets=datasets_schema,
        selected_dataset=selected_dataset,
    )


@router.get("/api/public/leaderboard")
def public_leaderboard(request: Request) -> dict[str, object]:
    settings = get_web_settings(request)
    return build_public_leaderboard_artifact(
        ledger_root=settings.ledger_root,
        tasks_root=settings.tasks_root,
    )


@router.get("/api/internal/leaderboard", dependencies=[Depends(require_internal_access)])
def internal_leaderboard(request: Request) -> dict[str, object]:
    settings = get_web_settings(request)
    return build_internal_leaderboard_artifact(
        ledger_root=settings.ledger_root,
        tasks_root=settings.tasks_root,
    )
