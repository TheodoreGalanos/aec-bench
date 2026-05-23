# ABOUTME: Coordination boundary for evaluation summaries over imported TrialRecords.
# ABOUTME: Keeps pure summary computation together and makes judge-readiness policy explicit.

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any

from aec_bench.contracts.evaluation_result import ConfidenceMetadata
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.evaluation.aggregation import BehavioralTraceClassifier, summarize_behavioral_records
from aec_bench.evaluation.stats import mean
from aec_bench.evaluation.trace_summary import summarize_trial_traces


@dataclass(frozen=True)
class AutomatedJudgmentReadiness:
    ready: bool
    reasons: tuple[str, ...]
    calibration_sample_size: int
    calibration_agreement: float | None
    confidence: ConfidenceMetadata | None

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        confidence = payload["confidence"]
        if isinstance(confidence, ConfidenceMetadata):
            payload["confidence"] = confidence.model_dump(exclude_none=True)
        # asdict preserves tuples; convert to list for JSON compatibility
        payload["reasons"] = list(self.reasons)
        return payload


def summarize_evaluation_records(
    records: list[TrialRecord],
    *,
    behavioral_classifier: BehavioralTraceClassifier | None = None,
    automated_judgment_confidence: ConfidenceMetadata | None = None,
    calibration_sample_size: int = 0,
    calibration_agreement: float | None = None,
) -> dict[str, Any]:
    n_trials = len(records)
    rewards = [record.evaluation.reward for record in records]
    total_cost = sum(record.cost.estimated_cost_usd or 0.0 for record in records if record.cost is not None)

    summary: dict[str, Any] = {
        "n_trials": n_trials,
        "mean_reward": mean(rewards),
        "total_cost_usd": total_cost,
        "by_adapter": _group_summary(records, key_fn=lambda record: record.agent.adapter),
        "by_task_prefix": _group_summary(
            records,
            key_fn=lambda record: record.task.task_id.split("/", 1)[0],
        ),
        "by_experiment": _group_summary(records, key_fn=lambda record: record.experiment_id),
        "trace": summarize_trial_traces(records),
    }
    if behavioral_classifier is not None:
        summary["behavioral"] = summarize_behavioral_records(
            records,
            classifier=behavioral_classifier,
        )
    summary["automated_judgment"] = assess_automated_judgment_readiness(
        confidence=automated_judgment_confidence,
        calibration_sample_size=calibration_sample_size,
        calibration_agreement=calibration_agreement,
    ).to_dict()
    return summary


def assess_automated_judgment_readiness(
    *,
    confidence: ConfidenceMetadata | None,
    calibration_sample_size: int,
    calibration_agreement: float | None,
    minimum_annotators: int = 2,
    minimum_inter_rater_agreement: float = 0.8,
    minimum_calibration_sample_size: int = 12,
    minimum_calibration_agreement: float = 0.8,
    maximum_confidence_interval_width: float = 0.2,
) -> AutomatedJudgmentReadiness:
    reasons: list[str] = []

    if confidence is None:
        reasons.append("missing_confidence_metadata")
    else:
        if (confidence.annotator_count or 0) < minimum_annotators:
            reasons.append("annotator_count_below_threshold")
        if (confidence.inter_rater_agreement or 0.0) < minimum_inter_rater_agreement:
            reasons.append("inter_rater_agreement_below_threshold")
        interval = confidence.confidence_interval
        if interval is None:
            reasons.append("missing_confidence_interval")
        elif interval[1] - interval[0] > maximum_confidence_interval_width:
            reasons.append("confidence_interval_too_wide")

    if calibration_sample_size < minimum_calibration_sample_size:
        reasons.append("calibration_sample_size_below_threshold")
    if (calibration_agreement or 0.0) < minimum_calibration_agreement:
        reasons.append("calibration_agreement_below_threshold")

    return AutomatedJudgmentReadiness(
        ready=not reasons,
        reasons=tuple(reasons),
        calibration_sample_size=calibration_sample_size,
        calibration_agreement=calibration_agreement,
        confidence=confidence,
    )


def _group_summary(
    records: list[TrialRecord],
    *,
    key_fn: Callable[[TrialRecord], str],
) -> dict[str, dict[str, float | int]]:
    grouped: dict[str, list[TrialRecord]] = defaultdict(list)
    for record in records:
        grouped[str(key_fn(record))].append(record)
    result: dict[str, dict[str, float | int]] = {}
    for key, group_records in sorted(grouped.items()):
        rewards = [record.evaluation.reward for record in group_records]
        n = len(rewards)
        result[key] = {
            "n_trials": n,
            "mean_reward": mean(rewards),
            "perfect_rate": sum(1 for r in rewards if r >= 1.0) / n if n else 0.0,
            "zero_rate": sum(1 for r in rewards if r <= 0.0) / n if n else 0.0,
            "total_cost_usd": sum(
                record.cost.estimated_cost_usd or 0.0 for record in group_records if record.cost is not None
            ),
        }
    return result
