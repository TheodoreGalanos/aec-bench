# ABOUTME: Tests reward-independent semantic transition metrics for staged evidence lifecycles.
# ABOUTME: Covers acquisition, update precision and recall, retention, interference, and empty support.

from __future__ import annotations

import pytest
from pydantic import ValidationError

from aec_bench.meta_harness.evidence_lifecycle_metrics import (
    LifecycleSemanticMetrics,
    LifecycleSemanticStateAccuracy,
    score_semantic_transitions,
)


def test_semantic_transition_metrics_score_exact_updates_and_retention() -> None:
    expected = {
        "initial_review": {"revision": "A", "stable": "accepted"},
        "response_review": {"revision": "B", "stable": "accepted", "finding": "open"},
        "closeout_review": {"revision": "B", "stable": "accepted", "finding": "closed"},
    }

    metrics = score_semantic_transitions(
        checkpoint_ids=("initial_review", "response_review", "closeout_review"),
        expected=expected,
        actual=expected,
    )

    assert metrics.initial.correct_atoms == 2
    assert metrics.initial.total_atoms == 2
    assert metrics.initial.accuracy == 1.0
    assert [transition.expected_update_count for transition in metrics.transitions] == [2, 1]
    assert [transition.stable_correct_before_count for transition in metrics.transitions] == [1, 2]
    assert metrics.aggregate.expected_update_count == 3
    assert metrics.aggregate.actual_update_count == 3
    assert metrics.aggregate.acquired_update_count == 3
    assert metrics.aggregate.acquisition == 1.0
    assert metrics.aggregate.update_precision == 1.0
    assert metrics.aggregate.update_recall == 1.0
    assert metrics.aggregate.update_f1 == 1.0
    assert metrics.aggregate.retention == 1.0
    assert metrics.aggregate.interference_count == 0


def test_semantic_transition_metrics_localize_missed_and_unsupported_changes() -> None:
    expected = {
        "initial_review": {"changing": "old", "stable": "accepted"},
        "response_review": {"changing": "new", "stable": "accepted"},
    }
    actual = {
        "initial_review": {"changing": "old", "stable": "accepted"},
        "response_review": {"changing": "old", "stable": "damaged"},
    }

    metrics = score_semantic_transitions(
        checkpoint_ids=("initial_review", "response_review"),
        expected=expected,
        actual=actual,
    )
    transition = metrics.transitions[0]

    assert transition.expected_update_count == 1
    assert transition.actual_update_count == 1
    assert transition.aligned_update_count == 0
    assert transition.acquired_update_count == 0
    assert transition.unsupported_update_count == 1
    assert transition.update_precision == 0.0
    assert transition.update_recall == 0.0
    assert transition.update_f1 == 0.0
    assert transition.stable_correct_before_count == 1
    assert transition.retained_count == 0
    assert transition.interference_count == 1
    assert transition.retention == 0.0
    assert transition.interference == 1.0


def test_semantic_transition_metrics_do_not_credit_premature_state_as_acquisition() -> None:
    expected = {
        "initial_review": {"revision": "A", "stable": "accepted"},
        "response_review": {"revision": "B", "stable": "accepted"},
    }
    actual = {
        "initial_review": {"revision": "B", "stable": "accepted"},
        "response_review": {"revision": "B", "stable": "accepted"},
    }

    metrics = score_semantic_transitions(
        checkpoint_ids=("initial_review", "response_review"),
        expected=expected,
        actual=actual,
    )
    transition = metrics.transitions[0]

    assert metrics.initial.accuracy == 0.5
    assert transition.expected_update_count == 1
    assert transition.actual_update_count == 0
    assert transition.acquired_update_count == 0
    assert transition.acquisition == 0.0
    assert transition.update_recall == 1.0
    assert transition.update_precision is None


def test_semantic_transition_metrics_credit_recovery_without_calling_it_acquisition() -> None:
    expected = {
        "initial_review": {"changed_by_evidence": "old", "stable": "accepted"},
        "response_review": {"changed_by_evidence": "new", "stable": "accepted"},
    }
    actual = {
        "initial_review": {"changed_by_evidence": "old", "stable": "mistaken"},
        "response_review": {"changed_by_evidence": "new", "stable": "accepted"},
    }

    metrics = score_semantic_transitions(
        checkpoint_ids=("initial_review", "response_review"),
        expected=expected,
        actual=actual,
    )
    transition = metrics.transitions[0]

    assert transition.actual_update_count == 2
    assert transition.aligned_update_count == 2
    assert transition.update_precision == 1.0
    assert transition.acquired_update_count == 1
    assert transition.acquisition == 1.0
    assert transition.stable_correct_before_count == 0
    assert transition.retention is None


def test_semantic_transition_metrics_compare_reference_lists_as_sets() -> None:
    expected = {
        "initial_review": {"closure_refs": ["DOC-A", "DOC-B"]},
        "response_review": {"closure_refs": ["DOC-A", "DOC-B", "DOC-C"]},
    }
    actual = {
        "initial_review": {"closure_refs": ["DOC-B", "DOC-A", "DOC-A"]},
        "response_review": {"closure_refs": ["DOC-C", "DOC-B", "DOC-A", "DOC-C"]},
    }

    metrics = score_semantic_transitions(
        checkpoint_ids=("initial_review", "response_review"),
        expected=expected,
        actual=actual,
    )

    assert metrics.initial.accuracy == 1.0
    assert metrics.transitions[0].acquisition == 1.0
    assert metrics.transitions[0].update_precision == 1.0


def test_semantic_transition_metrics_distinguish_boolean_and_integer_values() -> None:
    expected = {"initial_review": {"state": True}}
    actual = {"initial_review": {"state": 1}}

    metrics = score_semantic_transitions(
        checkpoint_ids=("initial_review",),
        expected=expected,
        actual=actual,
    )

    assert metrics.initial.accuracy == 0.0


def test_semantic_metric_contract_rejects_rate_that_does_not_match_support() -> None:
    with pytest.raises(ValidationError, match="accuracy must match"):
        LifecycleSemanticStateAccuracy(correct_atoms=1, total_atoms=2, accuracy=1.0)


def test_semantic_metric_contract_rejects_aggregate_that_does_not_match_transitions() -> None:
    states = {
        "initial_review": {"revision": "A"},
        "response_review": {"revision": "B"},
    }
    payload = score_semantic_transitions(
        checkpoint_ids=("initial_review", "response_review"),
        expected=states,
        actual=states,
    ).model_dump(mode="json")
    payload["aggregate"] = {
        "expected_update_count": 0,
        "actual_update_count": 0,
        "aligned_update_count": 0,
        "updated_to_expected_count": 0,
        "acquired_update_count": 0,
        "unsupported_update_count": 0,
        "stable_correct_before_count": 0,
        "retained_count": 0,
        "interference_count": 0,
        "acquisition": None,
        "update_precision": None,
        "update_recall": None,
        "update_f1": None,
        "retention": None,
        "interference": None,
    }

    with pytest.raises(ValidationError, match="aggregate must equal"):
        LifecycleSemanticMetrics.model_validate(payload)


def test_semantic_transition_metrics_use_null_for_zero_opportunity_rates() -> None:
    states = {"initial_review": {"stable": "accepted"}}

    metrics = score_semantic_transitions(
        checkpoint_ids=("initial_review",),
        expected=states,
        actual=states,
    )

    assert metrics.transitions == []
    assert metrics.aggregate.expected_update_count == 0
    assert metrics.aggregate.actual_update_count == 0
    assert metrics.aggregate.stable_correct_before_count == 0
    assert metrics.aggregate.acquisition is None
    assert metrics.aggregate.update_precision is None
    assert metrics.aggregate.update_recall is None
    assert metrics.aggregate.update_f1 is None
    assert metrics.aggregate.retention is None
    assert metrics.aggregate.interference is None
