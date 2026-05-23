# ABOUTME: Pivot endpoint aggregating trial records into rows × cols × metric tables.
# ABOUTME: Supports single- or multi-metric output; multi only when cols="none".

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, status

from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.ledger.reader import read_trial_records
from aec_bench.web.dependencies import get_web_settings
from aec_bench.web.schemas import AnalyzeCell, AnalyzeResponse
from aec_bench.web.utils import extract_discipline, extract_task_prefix

router = APIRouter()

Dim = Literal["experiment", "adapter", "model", "task_type", "discipline", "dataset"]
Col = Literal["experiment", "adapter", "model", "task_type", "discipline", "dataset", "none"]
Metric = Literal["mean_reward", "perfect_pct", "zero_pct", "count", "cost"]

_ALL_DIMS: tuple[Dim, ...] = (
    "experiment",
    "adapter",
    "model",
    "task_type",
    "discipline",
    "dataset",
)
_ALL_METRICS: tuple[Metric, ...] = ("mean_reward", "perfect_pct", "zero_pct", "count", "cost")


def _extract_dim(record: TrialRecord, dim: Dim) -> str | None:
    """Extract the label for a given dimension from a trial record."""
    if dim == "experiment":
        return record.experiment_id
    if dim == "adapter":
        return record.agent.adapter
    if dim == "model":
        return record.agent.model
    if dim == "task_type":
        prefix = extract_task_prefix(record.task.task_id)
        return prefix or None
    if dim == "discipline":
        disc = extract_discipline(record.task.task_id)
        return disc or None
    if dim == "dataset":
        return record.dataset_id
    return None


def _compute_cell(records: Sequence[TrialRecord], metrics: Sequence[Metric]) -> AnalyzeCell:
    """Reduce a bucket of records into an AnalyzeCell for the requested metrics."""
    count = len(records)
    cell = AnalyzeCell(count=count)
    if count == 0:
        return cell
    rewards = [r.evaluation.reward for r in records]
    if "mean_reward" in metrics:
        cell.mean_reward = sum(rewards) / count
    if "perfect_pct" in metrics:
        cell.perfect_pct = sum(1 for r in rewards if r == 1.0) / count
    if "zero_pct" in metrics:
        cell.zero_pct = sum(1 for r in rewards if r == 0.0) / count
    if "cost" in metrics:
        costs = [
            r.cost.estimated_cost_usd for r in records if r.cost is not None and r.cost.estimated_cost_usd is not None
        ]
        cell.cost = sum(costs) / len(costs) if costs else None
    return cell


def _apply_filters(
    records: Sequence[TrialRecord],
    *,
    experiment: str | None,
    dataset: str | None,
    model: str | None,
    adapter: str | None,
    task_type: str | None,
) -> list[TrialRecord]:
    out = list(records)
    if experiment:
        out = [r for r in out if r.experiment_id == experiment]
    if dataset:
        out = [r for r in out if r.dataset_id == dataset]
    if model:
        out = [r for r in out if r.agent.model == model]
    if adapter:
        out = [r for r in out if r.agent.adapter == adapter]
    if task_type:
        out = [r for r in out if _extract_dim(r, "task_type") == task_type]
    return out


def _parse_metrics(raw: str) -> list[Metric]:
    """Parse comma-separated metric list; reject unknown metrics."""
    if not raw:
        return ["mean_reward"]
    out: list[Metric] = []
    for token in raw.split(","):
        m = token.strip()
        if m not in _ALL_METRICS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown metric: {m!r}",
            )
        out.append(m)  # type: ignore[arg-type]
    return out


@router.get("/api/analyze")
def analyze_api(
    request: Request,
    rows: Dim = "adapter",
    cols: Col = "task_type",
    metrics: str = "mean_reward",
    delta: bool = False,
    experiment: str | None = None,
    dataset: str | None = None,
    model: str | None = None,
    adapter: str | None = None,
    task_type: str | None = None,
) -> AnalyzeResponse:
    if rows == cols:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="rows and cols must differ",
        )
    metric_list = _parse_metrics(metrics)
    # Multi-metric is only valid when cols="none".
    if len(metric_list) > 1 and cols != "none":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Multiple metrics are only allowed when cols='none'",
        )

    settings = get_web_settings(request)
    records = _apply_filters(
        read_trial_records(settings.ledger_root),
        experiment=experiment,
        dataset=dataset,
        model=model,
        adapter=adapter,
        task_type=task_type,
    )

    # Bucket by (row, col). When cols="none", col label is the empty string.
    buckets: dict[tuple[str, str], list[TrialRecord]] = defaultdict(list)
    row_bucket: dict[str, list[TrialRecord]] = defaultdict(list)
    col_bucket: dict[str, list[TrialRecord]] = defaultdict(list)
    for r in records:
        row_label = _extract_dim(r, rows)
        if row_label is None:
            continue
        col_label = "" if cols == "none" else _extract_dim(r, cols)  # type: ignore[arg-type]
        if col_label is None:
            continue
        buckets[(row_label, col_label)].append(r)
        row_bucket[row_label].append(r)
        if cols != "none":
            col_bucket[col_label].append(r)

    row_labels = sorted(row_bucket.keys())
    col_labels = sorted(col_bucket.keys()) if cols != "none" else []

    cells = {f"{row}|{col}": _compute_cell(recs, metric_list) for (row, col), recs in buckets.items()}
    row_totals = {row: _compute_cell(recs, metric_list) for row, recs in row_bucket.items()}
    col_totals = {col: _compute_cell(recs, metric_list) for col, recs in col_bucket.items()}
    grand_total = _compute_cell(records, metric_list)

    # Delta column: only meaningful with single metric and cols != "none" (>=2 cols).
    row_deltas: dict[str, float] | None = None
    if delta and len(metric_list) == 1 and cols != "none" and len(col_labels) >= 2:
        primary = metric_list[0]
        baseline_col = col_labels[0]
        last_col = col_labels[-1]
        row_deltas = {}
        for row in row_labels:
            base = getattr(cells.get(f"{row}|{baseline_col}"), primary, None)
            last = getattr(cells.get(f"{row}|{last_col}"), primary, None)
            if isinstance(base, int | float) and isinstance(last, int | float):
                row_deltas[row] = last - base

    return AnalyzeResponse(
        rows_dim=rows,
        cols_dim=cols,
        metrics=list(metric_list),
        delta_enabled=bool(row_deltas),
        row_labels=row_labels,
        col_labels=col_labels,
        cells=cells,
        row_totals=row_totals,
        col_totals=col_totals,
        grand_total=grand_total,
        row_deltas=row_deltas,
    )
