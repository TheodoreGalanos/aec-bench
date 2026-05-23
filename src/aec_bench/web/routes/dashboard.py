# ABOUTME: Public dashboard routes for the Phase 7 communication web layer.
# ABOUTME: Renders experiment hub with summary stats and experiment cards.

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from fastapi import APIRouter, Request

from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.ledger.reader import read_trial_records
from aec_bench.web.dependencies import get_web_settings
from aec_bench.web.schemas import DashboardResponse, ExperimentSummarySchema

router = APIRouter()


@dataclass(frozen=True)
class ExperimentSummary:
    """Aggregated stats for a single experiment."""

    experiment_id: str
    trial_count: int
    mean_reward: float
    models: Sequence[str]
    disciplines: Sequence[str]
    adapters: Sequence[str] = ()


def _aggregate_experiments(records: Sequence[TrialRecord]) -> list[ExperimentSummary]:
    """Group trial records by experiment_id and compute summary stats."""
    grouped: dict[str, list[TrialRecord]] = defaultdict(list)
    for record in records:
        grouped[record.experiment_id].append(record)

    summaries: list[ExperimentSummary] = []
    for experiment_id, trials in sorted(grouped.items()):
        rewards = [t.evaluation.reward for t in trials]
        mean_reward = sum(rewards) / len(rewards) if rewards else 0.0
        models = sorted({t.agent.model for t in trials})
        adapters = sorted({t.agent.adapter for t in trials})
        disciplines = sorted({t.task.task_id.split("/")[0] for t in trials if "/" in t.task.task_id})
        summaries.append(
            ExperimentSummary(
                experiment_id=experiment_id,
                trial_count=len(trials),
                mean_reward=round(mean_reward, 3),
                models=models,
                disciplines=disciplines,
                adapters=adapters,
            )
        )
    return summaries


def _count_annotated(records: Sequence[TrialRecord]) -> int:
    """Count trials that have at least one human annotation."""
    return sum(1 for r in records if r.evaluation.annotations is not None and len(r.evaluation.annotations) > 0)


@router.get("/api/dashboard")
def dashboard_api(
    request: Request,
    sort: str | None = None,
) -> DashboardResponse:
    settings = get_web_settings(request)
    records = read_trial_records(settings.ledger_root)
    experiments = _aggregate_experiments(records)
    total_trials = len(records)
    total_experiments = len(experiments)
    all_rewards = [r.evaluation.reward for r in records]
    mean_reward = round(sum(all_rewards) / len(all_rewards), 3) if all_rewards else 0.0
    annotated_count = _count_annotated(records)

    if sort:
        if sort == "name_asc":
            experiments.sort(key=lambda e: e.experiment_id)
        elif sort == "name_desc":
            experiments.sort(key=lambda e: e.experiment_id, reverse=True)
        elif sort == "trials_asc":
            experiments.sort(key=lambda e: e.trial_count)
        elif sort == "trials_desc":
            experiments.sort(key=lambda e: e.trial_count, reverse=True)
        elif sort == "reward_asc":
            experiments.sort(key=lambda e: e.mean_reward)
        elif sort == "reward_desc":
            experiments.sort(key=lambda e: e.mean_reward, reverse=True)

    return DashboardResponse(
        experiments=[
            ExperimentSummarySchema(
                experiment_id=e.experiment_id,
                trial_count=e.trial_count,
                mean_reward=e.mean_reward,
                models=list(e.models),
                disciplines=list(e.disciplines),
                adapters=list(e.adapters),
            )
            for e in experiments
        ],
        total_trials=total_trials,
        total_experiments=total_experiments,
        mean_reward=mean_reward,
        annotated_count=annotated_count,
    )
