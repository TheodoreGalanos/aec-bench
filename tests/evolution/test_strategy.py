# ABOUTME: Tests for SelectionStrategy protocol and HillClimbStrategy implementation.
# ABOUTME: Verifies hill-climb parent tracking, snapshot storage, and score updates.

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from aec_bench.contracts.evolution import (
    EvolutionCycleRecord,
    GateDecision,
    MutationSummary,
    WorkspaceSnapshot,
)
from aec_bench.evolution.archive_agent import SelectionResult
from aec_bench.evolution.graveyard import MutationGraveyard
from aec_bench.evolution.strategy import HillClimbStrategy, QDStrategy, SelectionStrategy

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_snapshot(version: str = "evo-1") -> WorkspaceSnapshot:
    return WorkspaceSnapshot(
        system_prompt="You are an agent.",
        skills=[],
        workspace_version=version,
    )


def _make_cycle_record(
    cycle: int = 1,
    version_before: str = "evo-0",
    version_after: str = "evo-1",
    batch_score: float = 0.5,
    gate: GateDecision = GateDecision.ACCEPTED,
) -> EvolutionCycleRecord:
    return EvolutionCycleRecord(
        cycle=cycle,
        workspace_version_before=version_before,
        workspace_version_after=version_after,
        batch_score=batch_score,
        structural_score=None,
        mutation=MutationSummary(prompt_modified=True),
        gate_decision=gate,
        trial_ids=["trial-001"],
        timestamp=datetime.now(tz=UTC),
    )


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


def test_hill_climb_satisfies_protocol() -> None:
    """HillClimbStrategy must be a structural subtype of SelectionStrategy."""
    strategy: SelectionStrategy = HillClimbStrategy()
    assert strategy is not None


# ---------------------------------------------------------------------------
# HillClimbStrategy tests
# ---------------------------------------------------------------------------


class TestHillClimbStrategy:
    def test_select_parent_returns_none_initially(self) -> None:
        strategy = HillClimbStrategy()
        result = strategy.select_parent(current_score=0.0)
        assert result is None

    def test_select_parent_returns_best_after_cycle(self) -> None:
        strategy = HillClimbStrategy()
        snapshot = _make_snapshot("evo-1")
        record = _make_cycle_record(batch_score=0.6, version_after="evo-1")
        graveyard = MutationGraveyard()

        strategy.on_cycle_end(
            cycle_record=record,
            snapshot=snapshot,
            step_result_gate=GateDecision.ACCEPTED,
            score_history=[0.6],
            graveyard=graveyard,
        )

        result = strategy.select_parent(current_score=0.5)
        assert result is not None
        assert isinstance(result, SelectionResult)
        assert result.parent_version == "evo-1"
        assert result.strategy == "conservative"

    def test_best_updates_on_higher_score(self) -> None:
        strategy = HillClimbStrategy()
        graveyard = MutationGraveyard()

        # First cycle: score 0.5
        snap1 = _make_snapshot("evo-1")
        rec1 = _make_cycle_record(cycle=1, batch_score=0.5, version_after="evo-1")
        strategy.on_cycle_end(
            cycle_record=rec1,
            snapshot=snap1,
            step_result_gate=GateDecision.ACCEPTED,
            score_history=[0.5],
            graveyard=graveyard,
        )

        # Second cycle: higher score 0.8
        snap2 = _make_snapshot("evo-2")
        rec2 = _make_cycle_record(cycle=2, batch_score=0.8, version_after="evo-2")
        strategy.on_cycle_end(
            cycle_record=rec2,
            snapshot=snap2,
            step_result_gate=GateDecision.ACCEPTED,
            score_history=[0.5, 0.8],
            graveyard=graveyard,
        )

        result = strategy.select_parent(current_score=0.7)
        assert result is not None
        assert result.parent_version == "evo-2"

    def test_best_does_not_update_on_lower_score(self) -> None:
        strategy = HillClimbStrategy()
        graveyard = MutationGraveyard()

        # First cycle: score 0.8
        snap1 = _make_snapshot("evo-1")
        rec1 = _make_cycle_record(cycle=1, batch_score=0.8, version_after="evo-1")
        strategy.on_cycle_end(
            cycle_record=rec1,
            snapshot=snap1,
            step_result_gate=GateDecision.ACCEPTED,
            score_history=[0.8],
            graveyard=graveyard,
        )

        # Second cycle: lower score 0.4
        snap2 = _make_snapshot("evo-2")
        rec2 = _make_cycle_record(cycle=2, batch_score=0.4, version_after="evo-2")
        strategy.on_cycle_end(
            cycle_record=rec2,
            snapshot=snap2,
            step_result_gate=GateDecision.ACCEPTED,
            score_history=[0.8, 0.4],
            graveyard=graveyard,
        )

        result = strategy.select_parent(current_score=0.3)
        assert result is not None
        assert result.parent_version == "evo-1"

    def test_get_snapshot_returns_stored(self) -> None:
        strategy = HillClimbStrategy()
        graveyard = MutationGraveyard()

        snap = _make_snapshot("evo-1")
        rec = _make_cycle_record(batch_score=0.7, version_after="evo-1")
        strategy.on_cycle_end(
            cycle_record=rec,
            snapshot=snap,
            step_result_gate=GateDecision.ACCEPTED,
            score_history=[0.7],
            graveyard=graveyard,
        )

        retrieved = strategy.get_snapshot("evo-1")
        assert retrieved is not None
        assert retrieved.workspace_version == "evo-1"
        assert retrieved.system_prompt == "You are an agent."

    def test_get_snapshot_returns_none_for_unknown(self) -> None:
        strategy = HillClimbStrategy()
        result = strategy.get_snapshot("nonexistent")
        assert result is None

    def test_save_is_noop(self, tmp_path: Path) -> None:
        strategy = HillClimbStrategy()
        # Should not raise and should not create any files
        strategy.save(tmp_path)
        contents = list(tmp_path.iterdir())
        assert contents == []

    def test_summary_returns_mode(self) -> None:
        strategy = HillClimbStrategy()
        summary = strategy.summary()
        assert summary["mode"] == "hill_climb"

    def test_summary_includes_best_after_cycle(self) -> None:
        strategy = HillClimbStrategy()
        graveyard = MutationGraveyard()

        snap = _make_snapshot("evo-3")
        rec = _make_cycle_record(batch_score=0.75, version_after="evo-3")
        strategy.on_cycle_end(
            cycle_record=rec,
            snapshot=snap,
            step_result_gate=GateDecision.ACCEPTED,
            score_history=[0.75],
            graveyard=graveyard,
        )

        summary = strategy.summary()
        assert summary["best_version"] == "evo-3"
        assert summary["best_score"] == 0.75

    def test_on_cycle_end_accepts_extra_kwargs(self) -> None:
        """The **kwargs on on_cycle_end allows QD-specific params to be ignored."""
        strategy = HillClimbStrategy()
        graveyard = MutationGraveyard()

        snap = _make_snapshot("evo-1")
        rec = _make_cycle_record(batch_score=0.5, version_after="evo-1")
        strategy.on_cycle_end(
            cycle_record=rec,
            snapshot=snap,
            step_result_gate=GateDecision.ACCEPTED,
            score_history=[0.5],
            graveyard=graveyard,
            observations=[],  # extra kwarg — should be silently ignored
            run_id="test-run",  # another extra kwarg
        )

        result = strategy.select_parent(current_score=0.0)
        assert result is not None
        assert result.parent_version == "evo-1"


# ---------------------------------------------------------------------------
# QDStrategy protocol conformance
# ---------------------------------------------------------------------------


def test_qd_strategy_satisfies_protocol() -> None:
    """QDStrategy must be a structural subtype of SelectionStrategy."""
    strategy: SelectionStrategy = QDStrategy(evolver_model="claude-sonnet-4-6")
    assert strategy is not None


# ---------------------------------------------------------------------------
# QDStrategy tests
# ---------------------------------------------------------------------------


class TestQDStrategy:
    def test_select_parent_returns_none_when_archive_small(self) -> None:
        strategy = QDStrategy(evolver_model="claude-sonnet-4-6")
        assert strategy.select_parent(current_score=0.5) is None

    def test_on_cycle_end_inserts_into_archive(self) -> None:
        strategy = QDStrategy(evolver_model="claude-sonnet-4-6")
        snapshot = _make_snapshot("evo-1")
        record = _make_cycle_record(cycle=1, batch_score=0.5, version_after="evo-1")

        from aec_bench.contracts.evolution import (
            EvolutionObservation,
            ObservationEnrichment,
        )
        from tests.support.trial_record_factories import make_trial_record

        obs = EvolutionObservation(
            trial=make_trial_record(
                trial_id="t1",
                evaluation={
                    "reward": 0.5,
                    "validity": {
                        "output_parseable": True,
                        "schema_valid": True,
                        "verifier_completed": True,
                    },
                },
            ),
            enrichment=ObservationEnrichment(),
            workspace_version="evo-1",
            discipline="electrical",
        )

        strategy.on_cycle_end(
            cycle_record=record,
            snapshot=snapshot,
            step_result_gate=GateDecision.ACCEPTED,
            score_history=[0.5],
            graveyard=MutationGraveyard(),
            observations=[obs],
            run_id="test-run",
        )

        assert strategy.archive_size >= 1

    def test_get_snapshot_from_archive(self) -> None:
        """After inserting an observation, get_snapshot retrieves it."""
        strategy = QDStrategy(evolver_model="claude-sonnet-4-6")
        snapshot = _make_snapshot("evo-1")
        record = _make_cycle_record(cycle=1, batch_score=0.5, version_after="evo-1")

        from aec_bench.contracts.evolution import (
            EvolutionObservation,
            ObservationEnrichment,
        )
        from tests.support.trial_record_factories import make_trial_record

        obs = EvolutionObservation(
            trial=make_trial_record(
                trial_id="t1",
                evaluation={
                    "reward": 0.5,
                    "validity": {
                        "output_parseable": True,
                        "schema_valid": True,
                        "verifier_completed": True,
                    },
                },
            ),
            enrichment=ObservationEnrichment(),
            workspace_version="evo-1",
            discipline="electrical",
        )

        strategy.on_cycle_end(
            cycle_record=record,
            snapshot=snapshot,
            step_result_gate=GateDecision.ACCEPTED,
            score_history=[0.5],
            graveyard=MutationGraveyard(),
            observations=[obs],
            run_id="test-run",
        )

        retrieved = strategy.get_snapshot("evo-1")
        assert retrieved is not None

    def test_get_snapshot_returns_none_for_unknown(self) -> None:
        strategy = QDStrategy(evolver_model="claude-sonnet-4-6")
        assert strategy.get_snapshot("nonexistent") is None

    def test_save_persists_archive(self, tmp_path: Path) -> None:
        strategy = QDStrategy(evolver_model="claude-sonnet-4-6")
        strategy.save(tmp_path)
        assert (tmp_path / "archive.json").exists()

    def test_summary_returns_qd_mode(self) -> None:
        strategy = QDStrategy(evolver_model="claude-sonnet-4-6")
        s = strategy.summary()
        assert s["mode"] == "qd"
        assert "archive_size" in s
        assert "archive_summary" in s
