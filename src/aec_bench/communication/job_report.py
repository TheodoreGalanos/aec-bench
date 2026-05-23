# ABOUTME: Ledger-backed experiment reporting that mirrors legacy Harbor job summaries.
# ABOUTME: Builds stable summary, JSON, and CSV outputs from TrialRecord data only.

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from datetime import timedelta
from typing import Any

from aec_bench.communication.metrics import coerce_int, resolve_agent_name, split_task_id
from aec_bench.contracts.agent_output import AgentOutputStatus
from aec_bench.contracts.pricing import estimate_cost_usd
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.evaluation.aggregation import BehavioralTraceClassifier, summarize_behavioral_records


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int


@dataclass(frozen=True)
class TrialReport:
    trial_name: str
    task_name: str
    task_type: str
    reward: float
    tokens: TokenUsage
    cost_usd: float
    turns_used: int
    max_turns: int
    duration_sec: float
    model: str
    has_error: bool
    classified_turns: int | None = None
    dominant_bond: str | None = None
    mean_turn_confidence: float | None = None


@dataclass(frozen=True)
class TaskTypeSummary:
    task_type: str
    n_trials: int
    n_completed: int
    mean_reward: float
    n_perfect: int
    n_partial: int
    n_zero: int
    mean_turns: float
    pct_hit_max: float
    total_cost_usd: float
    mean_input_tokens: float
    mean_output_tokens: float
    mean_cache_read_tokens: float


@dataclass(frozen=True)
class ExperimentReport:
    experiment_id: str
    agent_name: str
    model_name: str
    started_at: str
    finished_at: str
    trials: list[TrialReport] = field(default_factory=list)
    by_task_type: dict[str, TaskTypeSummary] = field(default_factory=dict)
    overall_mean_reward: float = 0.0
    total_cost_usd: float = 0.0
    behavioral: dict[str, Any] | None = None


def trial_report_from_record(record: TrialRecord) -> TrialReport:
    task_type, task_name = split_task_id(record.task.task_id)
    agent_result = record.outputs.agent_result or {}
    fallback_output_tokens = (
        record.cost.tokens_out if record.cost is not None and record.cost.tokens_out is not None else 0
    )
    tokens = TokenUsage(
        input_tokens=coerce_int(agent_result.get("usage_input_tokens")),
        output_tokens=coerce_int(
            agent_result.get("usage_output_tokens"),
            fallback=fallback_output_tokens,
        ),
        cache_read_tokens=coerce_int(agent_result.get("usage_cache_tokens")),
        cache_write_tokens=coerce_int(agent_result.get("usage_cache_write_tokens")),
    )
    cost_usd = record.cost.estimated_cost_usd if record.cost is not None else None
    if cost_usd is None:
        cost_usd = estimate_cost_usd(
            record.agent.model,
            input_tokens=tokens.input_tokens,
            output_tokens=tokens.output_tokens,
            cache_read_tokens=tokens.cache_read_tokens,
            cache_write_tokens=tokens.cache_write_tokens,
        )

    return TrialReport(
        trial_name=record.trial_id,
        task_name=task_name,
        task_type=task_type,
        reward=record.evaluation.reward,
        tokens=tokens,
        cost_usd=cost_usd or 0.0,
        turns_used=coerce_int(agent_result.get("turns_used")),
        max_turns=coerce_int(agent_result.get("max_turns")),
        duration_sec=record.timing.agent_seconds or record.timing.total_seconds,
        model=record.agent.model,
        has_error=_has_error(record),
    )


def build_experiment_report(
    records: Sequence[TrialRecord],
    *,
    behavioral_classifier: BehavioralTraceClassifier | None = None,
) -> ExperimentReport:
    if not records:
        raise ValueError("cannot build experiment report from zero records")

    experiment_ids = {record.experiment_id for record in records}
    if len(experiment_ids) != 1:
        raise ValueError("experiment report requires records from exactly one experiment")

    trials = [trial_report_from_record(record) for record in records]
    behavioral: dict[str, Any] | None = None
    if behavioral_classifier is not None:
        behavioral = summarize_behavioral_records(
            list(records),
            classifier=behavioral_classifier,
        )
        trials = _attach_behavioral_trial_data(trials, behavioral)

    by_type: dict[str, list[TrialReport]] = {}
    for trial in trials:
        by_type.setdefault(trial.task_type, []).append(trial)

    summaries = {
        task_type: _summarize_task_type(task_type, task_trials) for task_type, task_trials in sorted(by_type.items())
    }
    completed_trials = [trial for trial in trials if not trial.has_error]
    started_at = min(record.timestamp for record in records)
    finished_at = max(record.timestamp + timedelta(seconds=record.timing.total_seconds) for record in records)
    first_record = records[0]

    return ExperimentReport(
        experiment_id=first_record.experiment_id,
        agent_name=resolve_agent_name(first_record),
        model_name=first_record.agent.model,
        started_at=started_at.isoformat(),
        finished_at=finished_at.isoformat(),
        trials=trials,
        by_task_type=summaries,
        overall_mean_reward=(
            sum(trial.reward for trial in completed_trials) / len(completed_trials) if completed_trials else 0.0
        ),
        total_cost_usd=sum(trial.cost_usd for trial in trials),
        behavioral=behavioral,
    )


def experiment_report_to_dict(report: ExperimentReport) -> dict[str, Any]:
    payload = {
        "experiment_id": report.experiment_id,
        "agent_name": report.agent_name,
        "model_name": report.model_name,
        "started_at": report.started_at,
        "finished_at": report.finished_at,
        "overall_mean_reward": round(report.overall_mean_reward, 4),
        "total_cost_usd": round(report.total_cost_usd, 4),
        "by_task_type": {task_type: asdict(summary) for task_type, summary in report.by_task_type.items()},
        "trials": [_trial_to_flat_dict(trial) for trial in report.trials],
    }
    if report.behavioral is not None:
        payload["behavioral"] = report.behavioral
    return payload


def _summarize_task_type(task_type: str, trials: Sequence[TrialReport]) -> TaskTypeSummary:
    completed = [trial for trial in trials if not trial.has_error]
    n_completed = len(completed)
    if n_completed == 0:
        return TaskTypeSummary(
            task_type=task_type,
            n_trials=len(trials),
            n_completed=0,
            mean_reward=0.0,
            n_perfect=0,
            n_partial=0,
            n_zero=0,
            mean_turns=0.0,
            pct_hit_max=0.0,
            total_cost_usd=sum(trial.cost_usd for trial in trials),
            mean_input_tokens=0.0,
            mean_output_tokens=0.0,
            mean_cache_read_tokens=0.0,
        )

    rewards = [trial.reward for trial in completed]
    n_perfect = sum(1 for reward in rewards if reward >= 1.0)
    n_zero = sum(1 for reward in rewards if reward <= 0.0)
    n_partial = n_completed - n_perfect - n_zero
    n_hit_max = sum(1 for trial in completed if trial.max_turns > 0 and trial.turns_used >= trial.max_turns)
    return TaskTypeSummary(
        task_type=task_type,
        n_trials=len(trials),
        n_completed=n_completed,
        mean_reward=sum(rewards) / n_completed,
        n_perfect=n_perfect,
        n_partial=n_partial,
        n_zero=n_zero,
        mean_turns=sum(trial.turns_used for trial in completed) / n_completed,
        pct_hit_max=n_hit_max / n_completed * 100,
        total_cost_usd=sum(trial.cost_usd for trial in trials),
        mean_input_tokens=(sum(trial.tokens.input_tokens for trial in completed) / n_completed),
        mean_output_tokens=(sum(trial.tokens.output_tokens for trial in completed) / n_completed),
        mean_cache_read_tokens=(sum(trial.tokens.cache_read_tokens for trial in completed) / n_completed),
    )


def _trial_to_flat_dict(
    trial: TrialReport,
    *,
    include_behavioral: bool = True,
) -> dict[str, Any]:
    payload = {
        "trial_name": trial.trial_name,
        "task_name": trial.task_name,
        "task_type": trial.task_type,
        "reward": trial.reward,
        "input_tokens": trial.tokens.input_tokens,
        "output_tokens": trial.tokens.output_tokens,
        "cache_read_tokens": trial.tokens.cache_read_tokens,
        "cache_write_tokens": trial.tokens.cache_write_tokens,
        "cost_usd": round(trial.cost_usd, 6),
        "turns_used": trial.turns_used,
        "max_turns": trial.max_turns,
        "duration_sec": round(trial.duration_sec, 2),
        "model": trial.model,
        "has_error": trial.has_error,
    }
    if include_behavioral:
        payload["classified_turns"] = trial.classified_turns
        payload["dominant_bond"] = trial.dominant_bond
        payload["mean_turn_confidence"] = trial.mean_turn_confidence
    return payload


def _attach_behavioral_trial_data(
    trials: Sequence[TrialReport],
    behavioral: dict[str, Any],
) -> list[TrialReport]:
    trials_by_name = {
        str(item.get("trial_id")): item for item in behavioral.get("trials", []) if isinstance(item, dict)
    }
    return [
        TrialReport(
            trial_name=trial.trial_name,
            task_name=trial.task_name,
            task_type=trial.task_type,
            reward=trial.reward,
            tokens=trial.tokens,
            cost_usd=trial.cost_usd,
            turns_used=trial.turns_used,
            max_turns=trial.max_turns,
            duration_sec=trial.duration_sec,
            model=trial.model,
            has_error=trial.has_error,
            classified_turns=_behavioral_int(
                trials_by_name.get(trial.trial_name),
                "classified_turns",
            ),
            dominant_bond=_behavioral_str(trials_by_name.get(trial.trial_name), "dominant_bond"),
            mean_turn_confidence=_behavioral_float(
                trials_by_name.get(trial.trial_name),
                "mean_turn_confidence",
            ),
        )
        for trial in trials
    ]


def _behavioral_int(payload: object, key: str) -> int | None:
    if not isinstance(payload, dict):
        return None
    value = payload.get(key)
    return int(value) if value is not None else None


def _behavioral_float(payload: object, key: str) -> float | None:
    if not isinstance(payload, dict):
        return None
    value = payload.get(key)
    return float(value) if value is not None else None


def _behavioral_str(payload: object, key: str) -> str | None:
    if not isinstance(payload, dict):
        return None
    value = payload.get(key)
    return value if isinstance(value, str) else None


def _has_error(record: TrialRecord) -> bool:
    agent_output = record.outputs.agent_output
    if agent_output is not None and agent_output.status is AgentOutputStatus.FAILED:
        return True
    agent_result = record.outputs.agent_result or {}
    if agent_result.get("provider_error"):
        return True
    harbor_status = agent_result.get("harbor_status")
    if isinstance(harbor_status, str) and harbor_status not in {"ok", "completed"}:
        return True
    return False
