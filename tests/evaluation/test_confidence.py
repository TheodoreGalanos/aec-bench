# ABOUTME: Tests the pure behavioral confidence summarization helpers for evaluation.
# ABOUTME: Verifies completeness and low-confidence diagnostics stay deterministic.

import pytest

from aec_bench.evaluation.behavioral import BondType, ClassifiedTrace, TurnClassification
from aec_bench.evaluation.confidence import summarize_behavioral_confidence


def test_summarize_behavioral_confidence_reports_completeness_and_low_confidence_rates() -> None:
    classified_traces = [
        ClassifiedTrace(
            trace_id="trial-001",
            model_name="claude-sonnet-4-5",
            classifications=(
                TurnClassification(turn_index=1, bond_type=BondType.EXECUTION, confidence=0.9),
                TurnClassification(
                    turn_index=2,
                    bond_type=BondType.VERIFICATION,
                    confidence=0.8,
                ),
            ),
        ),
        ClassifiedTrace(
            trace_id="trial-002",
            model_name="claude-sonnet-4-5",
            classifications=(
                TurnClassification(
                    turn_index=1,
                    bond_type=BondType.EXPLORATION,
                    confidence=0.6,
                ),
                TurnClassification(turn_index=2, bond_type=BondType.EXECUTION, confidence=0.8),
            ),
        ),
    ]

    summary = summarize_behavioral_confidence(
        classified_traces,
        total_trials=3,
        low_confidence_threshold=0.75,
    )

    assert summary["confidence_method"] == "behavioral-turn-classifier"
    assert summary["classified_trials"] == 2
    assert summary["trials_with_behavioral_trace"] == 2
    assert summary["evaluation_completeness"] == pytest.approx(2.0 / 3.0)
    assert summary["mean_turn_confidence"] == pytest.approx(0.775)
    assert summary["mean_trial_confidence"] == pytest.approx(0.775)
    assert summary["low_confidence_turn_fraction"] == pytest.approx(0.25)
    assert summary["low_confidence_trial_fraction"] == pytest.approx(0.5)
    assert summary["low_confidence_threshold"] == pytest.approx(0.75)
    assert summary["metadata"] == {"confidence_method": "behavioral-turn-classifier"}
