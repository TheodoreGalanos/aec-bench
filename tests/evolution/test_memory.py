# ABOUTME: Tests bounded structured AVO memory retention and source identity validation.
# ABOUTME: Proves priority selection is deterministic without retaining provider conversation state.

from __future__ import annotations

import pytest

from aec_bench.evolution.memory import AVOMemoryEntry, retain_memory


def _entry(
    index: int,
    *,
    attempt_id: str | None = None,
    outcome: str = "not_improved",
    failure_category: str | None = None,
    next_direction: str | None = None,
) -> AVOMemoryEntry:
    return AVOMemoryEntry(
        source_variation_id="variation-1",
        source_attempt_id=attempt_id or f"attempt-{index}",
        hypothesis=f"hypothesis-{index}",
        change_summary=f"change-{index}",
        evidence_summary=f"evidence-{index}",
        outcome=outcome,
        failure_category=failure_category,
        next_direction=next_direction,
    )


def test_retention_keeps_best_failures_successful_direction_then_recent_entries() -> None:
    entries = (
        _entry(0, failure_category="old-failure"),
        _entry(1, failure_category="repeat-failure"),
        _entry(2, failure_category="repeat-failure"),
        _entry(3, failure_category="recent-failure"),
        _entry(4, outcome="improved", next_direction="older successful direction"),
        _entry(5),
        _entry(6, outcome="improved", next_direction="latest successful direction"),
        _entry(7, attempt_id="best-attempt"),
        _entry(8),
    )

    retained = retain_memory(entries, best_attempt_id="best-attempt", limit=6)

    assert tuple(entry.source_attempt_id for entry in retained) == (
        "attempt-0",
        "attempt-2",
        "attempt-3",
        "attempt-6",
        "best-attempt",
        "attempt-8",
    )


def test_retention_caps_more_than_24_entries_and_is_repeatable() -> None:
    entries = tuple(_entry(index) for index in range(30))

    first = retain_memory(entries, best_attempt_id="attempt-2")
    second = retain_memory(entries, best_attempt_id="attempt-2")

    assert first == second
    assert len(first) == 24
    assert first[0].source_attempt_id == "attempt-2"
    assert tuple(entry.source_attempt_id for entry in first[-3:]) == ("attempt-27", "attempt-28", "attempt-29")


def test_retention_keeps_successful_direction_when_next_direction_is_omitted() -> None:
    entries = tuple(_entry(index) for index in range(24)) + (_entry(24, outcome="improved"),)

    retained = retain_memory(entries)

    assert retained[-1].source_attempt_id == "attempt-24"


def test_memory_rejects_blank_values_and_duplicate_source_identity() -> None:
    with pytest.raises(ValueError, match="hypothesis must not be blank"):
        AVOMemoryEntry(
            source_variation_id="variation-1",
            source_attempt_id="attempt-0",
            hypothesis=" ",
            change_summary="change",
            evidence_summary="evidence",
            outcome="not_improved",
        )

    duplicate = _entry(1, attempt_id="attempt-0")
    with pytest.raises(ValueError, match="source variation and attempt IDs must be unique"):
        retain_memory((_entry(0), duplicate))
