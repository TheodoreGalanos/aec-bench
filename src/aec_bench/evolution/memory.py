# ABOUTME: Defines bounded structured memory facts for AVO variation calls.
# ABOUTME: Owns deterministic validation and retention without provider or transcript state.

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must not be blank")


AVO_MEMORY_LIMIT = 24
"""Maximum number of structured facts retained for one AVO session."""


class AVOMemoryOutcome(StrEnum):
    """Finite outcome labels emitted by the deterministic memory projector."""

    IMPROVED = "improved"
    NOT_IMPROVED = "not_improved"
    INVALID = "invalid"
    EVALUATION_ERROR = "evaluation_error"


@dataclass(frozen=True)
class AVOMemoryEntry:
    """One bounded, structured fact produced by an AVO evaluation."""

    source_variation_id: str
    source_attempt_id: str
    hypothesis: str
    change_summary: str
    evidence_summary: str
    outcome: AVOMemoryOutcome
    failure_category: str | None = None
    next_direction: str | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "source_variation_id",
            "source_attempt_id",
            "hypothesis",
            "change_summary",
            "evidence_summary",
            "outcome",
        ):
            _require_text(getattr(self, field_name), field_name)
        for field_name in ("failure_category", "next_direction"):
            value = getattr(self, field_name)
            if value is not None:
                _require_text(value, field_name)
        try:
            object.__setattr__(self, "outcome", AVOMemoryOutcome(self.outcome))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"unsupported memory outcome: {self.outcome!r}") from exc


def validate_memory_entries(entries: Sequence[AVOMemoryEntry]) -> tuple[AVOMemoryEntry, ...]:
    """Validate memory values and their source identity before retention."""
    values = tuple(entries)
    if any(not isinstance(entry, AVOMemoryEntry) for entry in values):
        raise TypeError("memory must contain AVOMemoryEntry values")
    identities = tuple((entry.source_variation_id, entry.source_attempt_id) for entry in values)
    if len(identities) != len(set(identities)):
        raise ValueError("memory source variation and attempt IDs must be unique")
    return values


def _is_successful_memory_outcome(outcome: AVOMemoryOutcome) -> bool:
    """Recognise stable successful outcome labels used by retention."""
    return outcome is AVOMemoryOutcome.IMPROVED


def retain_memory(
    entries: Sequence[AVOMemoryEntry],
    *,
    best_attempt_id: str | None = None,
    limit: int = AVO_MEMORY_LIMIT,
) -> tuple[AVOMemoryEntry, ...]:
    """Retain bounded facts by deterministic priority and source order.

    Input entries are chronological (oldest first). Priority selects the best
    current attempt, then the newest distinct failure categories, then the
    newest successful direction, and finally the newest remaining entries.
    The returned entries keep their original chronological order.
    """
    if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
        raise ValueError("memory limit must be a positive integer")
    if best_attempt_id is not None:
        _require_text(best_attempt_id, "best_attempt_id")
    values = validate_memory_entries(entries)
    if len(values) <= limit:
        return values

    selected: set[int] = set()
    if best_attempt_id is not None:
        best_indices = [index for index, entry in enumerate(values) if entry.source_attempt_id == best_attempt_id]
        selected.update(best_indices[-limit:])

    failure_categories: set[str] = set()
    for index in selected:
        category = values[index].failure_category
        if category is not None:
            failure_categories.add(category)
    for index in range(len(values) - 1, -1, -1):
        category = values[index].failure_category
        if category is None or category in failure_categories:
            continue
        selected.add(index)
        failure_categories.add(category)
        if len(selected) >= limit:
            break

    if len(selected) < limit:
        for index in range(len(values) - 1, -1, -1):
            entry = values[index]
            if index in selected or not _is_successful_memory_outcome(entry.outcome):
                continue
            selected.add(index)
            break

    if len(selected) < limit:
        for index in range(len(values) - 1, -1, -1):
            if index not in selected:
                selected.add(index)
                if len(selected) >= limit:
                    break

    return tuple(values[index] for index in sorted(selected))


__all__ = (
    "AVO_MEMORY_LIMIT",
    "AVOMemoryEntry",
    "AVOMemoryOutcome",
    "retain_memory",
    "validate_memory_entries",
)
