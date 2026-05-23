# ABOUTME: Trace query tool for the evolver LLM to drill into specific trace windows.
# ABOUTME: Filters turns by range, bond type, error state, or reasoning-only mode.

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from aec_bench.contracts.evolution import TraceQueryRequest, TraceSlice, TraceSliceTurn
from aec_bench.evaluation.behavioral import TurnClassification


def execute_trace_query(
    query: TraceQueryRequest,
    *,
    turns: Sequence[dict[str, Any]],
    classifications: Sequence[TurnClassification],
) -> TraceSlice:
    """Return a windowed subset of turns matching the query filters.

    Applies turn_range, bond_type_filter, errors_only, and reasoning_only
    filters in order, attaches bond_type and confidence from classifications,
    and returns a TraceSlice with a human-readable context string.
    """
    classification_map: dict[int, TurnClassification] = {c.turn_index: c for c in classifications}

    filtered: list[TraceSliceTurn] = []
    for turn in turns:
        turn_index: int = turn["turn_index"]

        if query.turn_range is not None:
            low, high = query.turn_range
            if turn_index < low or turn_index > high:
                continue

        if query.bond_type_filter is not None:
            classification = classification_map.get(turn_index)
            if classification is None or classification.bond_type != query.bond_type_filter:
                continue

        if query.errors_only and not turn.get("is_error", False):
            continue

        if query.reasoning_only and turn.get("tool_calls"):
            continue

        classification = classification_map.get(turn_index)
        filtered.append(
            TraceSliceTurn(
                turn_index=turn_index,
                role=turn["role"],
                content=turn["content"],
                tool_calls=list(turn.get("tool_calls", [])),
                tool_outputs=list(turn.get("tool_outputs", [])),
                is_error=bool(turn.get("is_error", False)),
                bond_type=classification.bond_type if classification is not None else None,
                bond_confidence=classification.confidence if classification is not None else None,
            )
        )

    context = _build_context_string(query, filtered_count=len(filtered), total_count=len(turns))

    return TraceSlice(
        trial_id=query.trial_id,
        turns=filtered,
        context=context,
    )


def _build_context_string(
    query: TraceQueryRequest,
    *,
    filtered_count: int,
    total_count: int,
) -> str:
    """Describe the applied filters in a short human-readable sentence."""
    parts: list[str] = [f"{filtered_count} of {total_count} turns"]

    if query.turn_range is not None:
        low, high = query.turn_range
        parts.append(f"range {low}-{high}")

    if query.bond_type_filter is not None:
        parts.append(f"filtered by {query.bond_type_filter.value}")

    if query.errors_only:
        parts.append("errors only")

    if query.reasoning_only:
        parts.append("reasoning only")

    return ", ".join(parts)
