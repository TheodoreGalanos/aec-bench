# ABOUTME: Enrichment pipeline that transforms TrialRecords into evolution-consumable formats.
# ABOUTME: Provides field score extraction from evaluation breakdowns and trace digest building.

from __future__ import annotations

from collections.abc import Sequence

from aec_bench.contracts.evolution import EvolutionObservation, FieldScore, ObservationEnrichment, TraceDigest
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.evaluation.behavioral import (
    BehavioralLLMClient,
    BondType,
    LLMTurnClassifier,
    TransitionMatrix,
    TurnClassification,
    load_behavioral_trace,
    score_trace_structural,
)

_BOND_SHORT: dict[BondType, str] = {
    BondType.EXECUTION: "E",
    BondType.VERIFICATION: "V",
    BondType.DELIBERATION: "D",
    BondType.EXPLORATION: "X",
}


def extract_field_scores(record: TrialRecord) -> list[FieldScore]:
    """Extract per-field rewards from a TrialRecord's evaluation breakdown.

    Returns an empty list when the breakdown is absent or empty. Only numeric
    values (int or float) are included; non-numeric entries are silently skipped.

    When the breakdown contains ``ground_truth`` and ``actual`` dicts, their
    values are included in the FieldScore for richer evolver feedback.
    """
    if record.evaluation is None:
        return []
    breakdown = record.evaluation.breakdown
    if not breakdown:
        return []

    ground_truth = breakdown.get("ground_truth", {})
    actual_values = breakdown.get("actual", {})

    field_scores: list[FieldScore] = []
    for field_name, value in breakdown.items():
        if field_name in ("ground_truth", "actual"):
            continue
        if not isinstance(value, int | float):
            continue

        expected_str = None
        actual_str = None
        if field_name in ground_truth:
            expected_str = str(ground_truth[field_name])
        if field_name in actual_values:
            actual_str = str(actual_values[field_name])

        field_scores.append(
            FieldScore(
                field_name=field_name,
                reward=float(value),
                expected=expected_str,
                actual=actual_str,
            )
        )
    return field_scores


def build_trace_digest(
    *,
    classifications: Sequence[TurnClassification],
    tool_call_count: int,
    tool_error_count: int,
    key_actions: list[str] | None = None,
    errors: list[str] | None = None,
    agent_reasoning: list[str] | None = None,
) -> TraceDigest:
    """Build a compressed trace representation from bond classifications.

    The bond_sequence is the short codes for each classification joined by hyphens,
    e.g. "E-E-V-D-E". Returns an empty string for empty classification sequences.
    """
    bond_sequence = "-".join(_BOND_SHORT[c.bond_type] for c in classifications)

    return TraceDigest(
        turn_count=len(classifications),
        tool_call_count=tool_call_count,
        tool_error_count=tool_error_count,
        bond_sequence=bond_sequence,
        key_actions=key_actions or [],
        errors=errors or [],
        agent_reasoning=agent_reasoning or [],
    )


def enrich_observations(
    observations: Sequence[EvolutionObservation],
    *,
    classifier_llm: BehavioralLLMClient,
    ideal_pattern: TransitionMatrix | None = None,
    ideal_sequence: tuple[BondType, ...] = (),
) -> tuple[EvolutionObservation, ...]:
    """Classify traces and attach enrichment without changing candidate identity."""
    classifier = LLMTurnClassifier(client=classifier_llm)
    result: list[EvolutionObservation] = []
    for observation in observations:
        if observation.enrichment.classified_trace is not None:
            result.append(observation)
            continue
        try:
            trace = load_behavioral_trace(observation.trial)
            classified = classifier.classify_trace(trace)
        except Exception:
            result.append(observation)
            continue
        structural_score = None
        if ideal_pattern is not None:
            structural_score = score_trace_structural(
                classified,
                ideal_matrix=ideal_pattern,
                ideal_sequence=ideal_sequence,
            )
        tool_call_count = sum(len(turn.tool_calls) for turn in trace.turns if turn.role == "assistant")
        tool_error_count = sum(sum(1 for item in turn.tool_results if item.is_error) for turn in trace.turns)
        key_actions: list[str] = []
        errors: list[str] = []
        reasoning: list[str] = []
        for turn in trace.turns:
            if turn.role == "assistant":
                for tool_call in turn.tool_calls:
                    summary = tool_call.tool_name
                    if tool_call.arguments:
                        summary = f"{summary}({str(dict(tool_call.arguments))[:150]})"
                    key_actions.append(summary)
                if turn.content and not turn.tool_calls:
                    reasoning.append(turn.content[:200])
            for tool_result in turn.tool_results:
                if tool_result.is_error and tool_result.output:
                    errors.append(tool_result.output[:300])
        enrichment = ObservationEnrichment(
            classified_trace=classified,
            structural_score=structural_score,
            field_scores=extract_field_scores(observation.trial),
            trace_digest=build_trace_digest(
                classifications=classified.classifications,
                tool_call_count=tool_call_count,
                tool_error_count=tool_error_count,
                key_actions=key_actions[:20],
                errors=errors[:10],
                agent_reasoning=reasoning[:10],
            ),
        )
        result.append(
            EvolutionObservation(
                trial=observation.trial,
                enrichment=enrichment,
                candidate_id=observation.candidate_id,
                discipline=observation.discipline,
            )
        )
    return tuple(result)
