# ABOUTME: Pure confidence helpers for classifier-driven behavioral evaluation outputs.
# ABOUTME: Summarizes completeness and low-confidence rates without mutating core contracts.

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from aec_bench.contracts.evaluation_result import ConfidenceMetadata
from aec_bench.evaluation.behavioral import ClassifiedTrace
from aec_bench.evaluation.stats import mean


@dataclass(frozen=True)
class BehavioralConfidenceSummary:
    confidence_method: str
    trials_with_behavioral_trace: int
    classified_trials: int
    evaluation_completeness: float
    mean_turn_confidence: float
    mean_trial_confidence: float
    low_confidence_turn_fraction: float
    low_confidence_trial_fraction: float
    low_confidence_threshold: float

    def to_dict(self) -> dict[str, object]:
        metadata = ConfidenceMetadata(confidence_method=self.confidence_method)
        return {
            "confidence_method": self.confidence_method,
            "trials_with_behavioral_trace": self.trials_with_behavioral_trace,
            "classified_trials": self.classified_trials,
            "evaluation_completeness": self.evaluation_completeness,
            "mean_turn_confidence": self.mean_turn_confidence,
            "mean_trial_confidence": self.mean_trial_confidence,
            "low_confidence_turn_fraction": self.low_confidence_turn_fraction,
            "low_confidence_trial_fraction": self.low_confidence_trial_fraction,
            "low_confidence_threshold": self.low_confidence_threshold,
            "metadata": metadata.model_dump(exclude_none=True),
        }


def summarize_behavioral_confidence(
    classified_traces: Sequence[ClassifiedTrace],
    *,
    total_trials: int,
    low_confidence_threshold: float = 0.75,
    confidence_method: str = "behavioral-turn-classifier",
) -> dict[str, object]:
    traces_with_classifications = [trace for trace in classified_traces if trace.classifications]
    turn_confidences = [
        classification.confidence for trace in traces_with_classifications for classification in trace.classifications
    ]
    trial_confidences = [
        mean(classification.confidence for classification in trace.classifications)
        for trace in traces_with_classifications
    ]
    low_confidence_turn_count = sum(1 for confidence in turn_confidences if confidence < low_confidence_threshold)
    low_confidence_trial_count = sum(1 for confidence in trial_confidences if confidence < low_confidence_threshold)
    summary = BehavioralConfidenceSummary(
        confidence_method=confidence_method,
        trials_with_behavioral_trace=len(classified_traces),
        classified_trials=len(traces_with_classifications),
        evaluation_completeness=(len(classified_traces) / total_trials if total_trials > 0 else 0.0),
        mean_turn_confidence=mean(turn_confidences),
        mean_trial_confidence=mean(trial_confidences),
        low_confidence_turn_fraction=(low_confidence_turn_count / len(turn_confidences) if turn_confidences else 0.0),
        low_confidence_trial_fraction=(
            low_confidence_trial_count / len(trial_confidences) if trial_confidences else 0.0
        ),
        low_confidence_threshold=low_confidence_threshold,
    )
    return summary.to_dict()
