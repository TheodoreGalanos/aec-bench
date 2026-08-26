# ABOUTME: Tests immutable state and outcome values for functional QD search.
# ABOUTME: Verifies identity, cardinality, status, and counter invariants at the value boundaries.

from dataclasses import FrozenInstanceError

import pytest

from aec_bench.contracts.evolution import MutationStrategy, WorkspaceSnapshot
from aec_bench.evolution.archive import (
    ArchiveBatchOutcome,
    ArchiveInsertionResult,
    ArchiveInsertionStatus,
)
from aec_bench.evolution.core import ResolvedSelection, SelectionPlan
from aec_bench.evolution.selection import (
    CellSelectionStat,
    CellSelectionState,
    QDState,
    StrategyBanditStat,
    StrategyBanditState,
)


def _snapshot(candidate_id: str) -> WorkspaceSnapshot:
    return WorkspaceSnapshot(system_prompt="Use engineering checks.", candidate_id=candidate_id)


def _plan(
    parent_candidate_id: str = "parent",
    inspiration_candidate_ids: tuple[str, ...] = ("inspiration",),
) -> SelectionPlan:
    return SelectionPlan(
        parent_candidate_id,
        inspiration_candidate_ids,
        MutationStrategy.CONSERVATIVE,
        "Improve checks",
        "Use the selected parent",
    )


def test_cell_selection_state_canonicalises_stats_and_rejects_duplicates() -> None:
    stat = CellSelectionStat(cell_index=2, selection_count=3, improvement_count=1, last_selected_cycle=4)
    state = CellSelectionState(stats=[stat])

    assert state.stats == (stat,)
    with pytest.raises(ValueError, match="unique cell indices"):
        CellSelectionState(stats=(stat, stat))


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"cell_index": -1}, "cell_index"),
        ({"selection_count": -1}, "selection_count"),
        ({"selection_count": 1, "improvement_count": 2}, "cannot exceed"),
        ({"last_selected_cycle": -1}, "last_selected_cycle"),
    ],
)
def test_cell_selection_stat_rejects_invalid_counters(kwargs: dict[str, int], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        CellSelectionStat(**{"cell_index": 0, **kwargs})


def test_strategy_bandit_state_canonicalises_stats_and_rejects_duplicates() -> None:
    stat = StrategyBanditStat(strategy="exploratory", attempts=2, successes=1)
    state = StrategyBanditState(stats=[stat])

    assert state.stats == (stat,)
    assert state.stats[0].strategy is MutationStrategy.EXPLORATORY
    with pytest.raises(ValueError, match="unique strategies"):
        StrategyBanditState(stats=(stat, stat))


def test_strategy_bandit_stat_rejects_invalid_strategy_counters() -> None:
    with pytest.raises(ValueError, match="cannot exceed"):
        StrategyBanditStat(strategy=MutationStrategy.CONSERVATIVE, attempts=1, successes=2)


def test_qd_state_is_frozen_and_validates_cycle() -> None:
    state = QDState(CellSelectionState(), StrategyBanditState(), None, cycle=0)

    with pytest.raises(FrozenInstanceError):
        state.cycle = 1  # type: ignore[misc]
    with pytest.raises(ValueError, match="non-negative"):
        QDState(CellSelectionState(), StrategyBanditState(), None, cycle=-1)


def test_resolved_selection_requires_exact_parent_and_inspiration_material() -> None:
    plan = _plan()
    resolved = ResolvedSelection(plan, _snapshot("parent"), (_snapshot("inspiration"),))

    assert resolved.inspirations[0].candidate_id == "inspiration"
    with pytest.raises(ValueError, match="resolved parent"):
        ResolvedSelection(plan, _snapshot("other"), (_snapshot("inspiration"),))
    with pytest.raises(ValueError, match="resolved inspirations"):
        ResolvedSelection(plan, _snapshot("parent"), ())


@pytest.mark.parametrize("status", list(ArchiveInsertionStatus))
def test_archive_insertion_result_accepts_each_status(status: ArchiveInsertionStatus) -> None:
    result = ArchiveInsertionResult(status, "candidate", 3, None)

    assert result.status is status
    assert result.candidate_id == "candidate"


def test_archive_insertion_result_rejects_invalid_identity_and_cell() -> None:
    with pytest.raises(ValueError, match="candidate_id must not be blank"):
        ArchiveInsertionResult(ArchiveInsertionStatus.NEW_CELL, " ", 1, None)
    with pytest.raises(ValueError, match="cell_index"):
        ArchiveInsertionResult(ArchiveInsertionStatus.NEW_CELL, "candidate", -1, None)


def test_archive_batch_outcome_reports_added_for_new_or_improved_insertions() -> None:
    rejected = ArchiveInsertionResult(ArchiveInsertionStatus.NOT_ADDED, "candidate", 2, None)
    improved = ArchiveInsertionResult(ArchiveInsertionStatus.IMPROVED, "candidate", 2, "previous")
    batch = ArchiveBatchOutcome("candidate", [rejected, improved])

    assert batch.insertions == (rejected, improved)
    assert batch.added is True
    assert ArchiveBatchOutcome("candidate", (rejected,)).added is False
    with pytest.raises(ValueError, match="match the batch"):
        ArchiveBatchOutcome("candidate", (ArchiveInsertionResult(ArchiveInsertionStatus.NEW_CELL, "other", 1, None),))
