# ABOUTME: Behavioral aggregation helpers for ledger-backed evaluation summaries in aec-bench.
# ABOUTME: Keeps classifier-driven enrichment explicit and separate from passive reporting paths.

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from typing import Protocol

from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.evaluation.behavioral import (
    BehavioralTrace,
    BehavioralTraceError,
    BondType,
    ClassifiedTrace,
    TransitionMatrix,
    build_ideal_pattern,
    build_ideal_sequence,
    load_behavioral_trace,
    score_trace_structural,
)
from aec_bench.evaluation.confidence import summarize_behavioral_confidence
from aec_bench.evaluation.stats import mean as _mean


class BehavioralTraceClassifier(Protocol):
    def classify_trace(self, trace: BehavioralTrace) -> ClassifiedTrace: ...


@dataclass(frozen=True)
class BehavioralTrialSummary:
    trial_id: str
    task_id: str
    reward: float
    classified_turns: int
    mean_turn_confidence: float | None
    bond_counts: dict[str, int]
    dominant_bond: str | None
    cosine_similarity: float | None = None
    edit_distance: int | None = None
    normalized_edit_distance: float | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class _ClassifiedRecord:
    record: TrialRecord
    trace: ClassifiedTrace


def build_behavioral_trial_summaries(
    records: list[TrialRecord],
    *,
    classifier: BehavioralTraceClassifier,
    reward_key: str = "reward",
    min_reward: float = 1.0,
) -> list[BehavioralTrialSummary]:
    classified_records = _classify_records(records, classifier)
    return _build_trial_summaries(
        classified_records,
        reward_key=reward_key,
        min_reward=min_reward,
    )


def summarize_behavioral_records(
    records: list[TrialRecord],
    *,
    classifier: BehavioralTraceClassifier,
    reward_key: str = "reward",
    min_reward: float = 1.0,
) -> dict[str, object]:
    classified_records = _classify_records(records, classifier)
    trial_summaries = _build_trial_summaries(
        classified_records,
        reward_key=reward_key,
        min_reward=min_reward,
    )
    total_classified_turns = sum(summary.classified_turns for summary in trial_summaries)
    bond_totals = {bond.value: sum(summary.bond_counts[bond.value] for summary in trial_summaries) for bond in BondType}
    dominant_bond_counts = Counter(
        summary.dominant_bond for summary in trial_summaries if summary.dominant_bond is not None
    )
    structural_summaries = [
        summary
        for summary in trial_summaries
        if summary.cosine_similarity is not None and summary.normalized_edit_distance is not None
    ]

    return {
        "n_trials": len(records),
        "trials_with_behavioral_trace": len(trial_summaries),
        "classified_trials": len(trial_summaries),
        "reference_trial_count": sum(
            1 for summary in trial_summaries if summary.reward >= min_reward and summary.classified_turns > 0
        ),
        "mean_classified_turns": _mean(summary.classified_turns for summary in trial_summaries),
        "bond_distribution": {
            bond: (count / total_classified_turns if total_classified_turns else 0.0)
            for bond, count in bond_totals.items()
        },
        "dominant_bond_counts": {
            bond: dominant_bond_counts[bond]
            for bond in (bond.value for bond in BondType)
            if dominant_bond_counts[bond] > 0
        },
        "mean_cosine_similarity": _mean(summary.cosine_similarity for summary in structural_summaries),
        "mean_normalized_edit_distance": _mean(summary.normalized_edit_distance for summary in structural_summaries),
        "confidence": summarize_behavioral_confidence(
            [item.trace for item in classified_records],
            total_trials=len(records),
        ),
        "trials": [summary.to_dict() for summary in trial_summaries],
    }


def _build_trial_summaries(
    classified_records: list[_ClassifiedRecord],
    *,
    reward_key: str,
    min_reward: float,
) -> list[BehavioralTrialSummary]:
    reference_traces = _reference_traces(
        classified_records,
        min_reward=min_reward,
    )
    ideal_matrix: TransitionMatrix | None = None
    ideal_sequence: tuple[BondType, ...] = ()
    if reference_traces:
        ideal_matrix = build_ideal_pattern(
            reference_traces,
            reward_key=reward_key,
            min_reward=min_reward,
        )
        ideal_sequence = build_ideal_sequence(
            reference_traces,
            reward_key=reward_key,
            min_reward=min_reward,
        )

    return [
        _trial_summary(
            item,
            ideal_matrix=ideal_matrix,
            ideal_sequence=ideal_sequence,
        )
        for item in classified_records
    ]


def _classify_records(
    records: list[TrialRecord],
    classifier: BehavioralTraceClassifier,
) -> list[_ClassifiedRecord]:
    classified_records: list[_ClassifiedRecord] = []
    for record in records:
        try:
            trace = load_behavioral_trace(record)
        except BehavioralTraceError:
            continue
        classified_records.append(_ClassifiedRecord(record=record, trace=classifier.classify_trace(trace)))
    return classified_records


def _reference_traces(
    classified_records: list[_ClassifiedRecord],
    *,
    min_reward: float,
) -> list[ClassifiedTrace]:
    return [
        item.trace
        for item in classified_records
        if item.record.evaluation.reward >= min_reward and item.trace.classifications
    ]


def _trial_summary(
    item: _ClassifiedRecord,
    *,
    ideal_matrix: TransitionMatrix | None,
    ideal_sequence: tuple[BondType, ...],
) -> BehavioralTrialSummary:
    bond_counts = {
        bond.value: sum(1 for classification in item.trace.classifications if classification.bond_type == bond)
        for bond in BondType
    }
    dominant_bond = _dominant_bond(bond_counts)

    cosine_similarity: float | None = None
    edit_distance: int | None = None
    normalized_edit_distance: float | None = None
    if ideal_matrix is not None and ideal_sequence and item.trace.classifications:
        structural_score = score_trace_structural(
            item.trace,
            ideal_matrix=ideal_matrix,
            ideal_sequence=ideal_sequence,
            reward=item.record.evaluation.reward,
        )
        cosine_similarity = structural_score.cosine_similarity
        edit_distance = structural_score.edit_distance
        normalized_edit_distance = structural_score.normalized_edit_distance

    return BehavioralTrialSummary(
        trial_id=item.record.trial_id,
        task_id=item.record.task.task_id,
        reward=item.record.evaluation.reward,
        classified_turns=len(item.trace.classifications),
        mean_turn_confidence=_mean(classification.confidence for classification in item.trace.classifications)
        if item.trace.classifications
        else None,
        bond_counts=bond_counts,
        dominant_bond=dominant_bond,
        cosine_similarity=cosine_similarity,
        edit_distance=edit_distance,
        normalized_edit_distance=normalized_edit_distance,
    )


_BOND_ORDER = {bond: index for index, bond in enumerate(BondType)}


def _dominant_bond(bond_counts: dict[str, int]) -> str | None:
    if not any(bond_counts.values()):
        return None
    return max(
        BondType,
        key=lambda bond: (bond_counts[bond.value], -_BOND_ORDER[bond]),
    ).value
