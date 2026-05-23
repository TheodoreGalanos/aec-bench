# ABOUTME: Pure helpers for extraction self-consistency in the lambda-rlm adapter.
# ABOUTME: Deterministically normalizes candidate values and vote-merges K extractions.

from __future__ import annotations

import math
from collections import Counter
from typing import Any


def normalise_value(value: Any) -> Any:
    """Return a deterministic, comparison-friendly form of a candidate value."""
    if isinstance(value, str):
        return " ".join(value.strip().lower().split())

    if isinstance(value, dict):
        return tuple((key, normalise_value(val)) for key, val in sorted(value.items(), key=lambda item: item[0]))

    if isinstance(value, list | tuple):
        items = [normalise_value(item) for item in value]
        return tuple(sorted(items, key=repr))

    return value


def vote_merge(
    candidates: list[dict[str, Any]],
    min_presence: int | None = None,
) -> tuple[dict[str, Any], dict[str, float]]:
    """Merge K extraction candidates by deterministic majority vote per field."""
    if not candidates:
        return {}, {}

    total_candidates = len(candidates)
    threshold = min_presence or math.ceil(total_candidates / 2)

    key_presence: Counter[str] = Counter()
    for candidate in candidates:
        key_presence.update(candidate.keys())

    consensus: dict[str, Any] = {}
    per_field_consistency: dict[str, float] = {}

    for key in sorted(key_presence):
        if key_presence[key] < threshold:
            continue

        votes: dict[Any, tuple[int, int, Any]] = {}
        for index, candidate in enumerate(candidates):
            if key not in candidate:
                continue

            raw_value = candidate[key]
            normalised = normalise_value(raw_value)
            count, first_index, original_value = votes.get(
                normalised,
                (0, index, raw_value),
            )
            votes[normalised] = (count + 1, first_index, original_value)

        winner_count = -1
        winner_index = total_candidates
        winner_value: Any = None
        for count, first_index, original_value in votes.values():
            if count > winner_count or (count == winner_count and first_index < winner_index):
                winner_count = count
                winner_index = first_index
                winner_value = original_value

        consensus[key] = winner_value
        per_field_consistency[key] = winner_count / total_candidates

    return consensus, per_field_consistency


def aggregate_consistency(per_field: dict[str, float]) -> float:
    """Aggregate per-field consistency scores to a single source score."""
    if not per_field:
        return 0.0

    return sum(per_field.values()) / len(per_field)
