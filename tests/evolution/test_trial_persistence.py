# ABOUTME: Tests for per-trial result persistence in evolution workspaces.
# ABOUTME: Covers extraction from observations, writing cycle JSONL files, and loading them back.

from __future__ import annotations

from pathlib import Path

from aec_bench.contracts.evaluation_result import EvaluationResult, ValidityCheck
from aec_bench.contracts.evolution import (
    EvolutionObservation,
    FieldScore,
    ObservationEnrichment,
    TraceDigest,
)
from aec_bench.contracts.trial_record import (
    TaskReference,
)
from aec_bench.evolution.trial_persistence import (
    extract_trial_outcome,
    load_cycle_trials,
    persist_cycle_trials,
)
from tests.support.trial_record_factories import make_trial_record

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_observation(
    trial_id: str = "trial-001",
    task_id: str = "electrical/voltage-drop/test-instance",
    reward: float = 1.0,
    field_scores: list[FieldScore] | None = None,
    trace_digest: TraceDigest | None = None,
) -> EvolutionObservation:
    """Build an EvolutionObservation for testing."""
    if field_scores is None:
        field_scores = [
            FieldScore(field_name="vc_mv_per_a_m", reward=1.0),
            FieldScore(field_name="voltage_drop_v", reward=1.0),
            FieldScore(field_name="voltage_drop_percent", reward=1.0),
            FieldScore(field_name="compliant", reward=1.0),
        ]
    if trace_digest is None:
        trace_digest = TraceDigest(
            turn_count=5,
            tool_call_count=3,
            tool_error_count=0,
            bond_sequence="EEDVV",
            key_actions=["read_file", "write_file"],
            errors=[],
        )
    trial = make_trial_record(
        trial_id=trial_id,
        task=TaskReference(task_id=task_id, task_revision="generated"),
        evaluation=EvaluationResult(
            reward=reward,
            validity=ValidityCheck(
                output_parseable=True,
                schema_valid=True,
                verifier_completed=True,
            ),
        ),
    )
    return EvolutionObservation(
        trial=trial,
        enrichment=ObservationEnrichment(
            field_scores=field_scores,
            trace_digest=trace_digest,
        ),
        workspace_version="evo-1",
        discipline="electrical",
    )


# ---------------------------------------------------------------------------
# Tests: extract_trial_outcome
# ---------------------------------------------------------------------------


class TestExtractTrialOutcome:
    def test_extracts_basic_fields(self) -> None:
        obs = _make_observation(trial_id="t1", task_id="elec/vd/inst-00", reward=0.75)

        outcome = extract_trial_outcome(obs)

        assert outcome.trial_id == "t1"
        assert outcome.task_id == "elec/vd/inst-00"
        assert outcome.discipline == "electrical"
        assert outcome.reward == 0.75

    def test_extracts_field_scores(self) -> None:
        obs = _make_observation(
            field_scores=[
                FieldScore(field_name="vc_mv_per_a_m", reward=1.0),
                FieldScore(field_name="voltage_drop_v", reward=0.0),
            ]
        )

        outcome = extract_trial_outcome(obs)

        assert outcome.field_scores == {"vc_mv_per_a_m": 1.0, "voltage_drop_v": 0.0}

    def test_extracts_trace_digest(self) -> None:
        obs = _make_observation(
            trace_digest=TraceDigest(
                turn_count=8,
                tool_call_count=5,
                tool_error_count=1,
                bond_sequence="EEEDVVE",
                errors=["file not found"],
            )
        )

        outcome = extract_trial_outcome(obs)

        assert outcome.turn_count == 8
        assert outcome.tool_call_count == 5
        assert outcome.tool_error_count == 1
        assert outcome.bond_sequence == "EEEDVVE"
        assert outcome.errors == ["file not found"]

    def test_handles_missing_trace_digest(self) -> None:
        """When the enrichment has no trace digest, zeroes are returned."""
        trial = make_trial_record(trial_id="no-trace")
        obs = EvolutionObservation(
            trial=trial,
            enrichment=ObservationEnrichment(trace_digest=None),
            workspace_version="evo-1",
            discipline="electrical",
        )

        outcome = extract_trial_outcome(obs)

        assert outcome.turn_count == 0
        assert outcome.tool_call_count == 0
        assert outcome.bond_sequence == ""

    def test_extracts_advisor_stats_from_cost_record(self) -> None:
        """Advisor stats on trial.cost should populate TrialOutcome's advisor fields."""
        from aec_bench.contracts.trial_record import CostRecord

        trial = make_trial_record(
            trial_id="with-advisor",
            cost=CostRecord(
                tokens_in=1000,
                tokens_out=500,
                advisor_calls=3,
                advisor_input_tokens=1500,
                advisor_output_tokens=400,
            ),
        )
        obs = EvolutionObservation(
            trial=trial,
            enrichment=ObservationEnrichment(trace_digest=None),
            workspace_version="evo-1",
            discipline="electrical",
        )

        outcome = extract_trial_outcome(obs)

        assert outcome.advisor_calls == 3
        assert outcome.advisor_input_tokens == 1500
        assert outcome.advisor_output_tokens == 400

    def test_advisor_stats_default_to_zero_without_cost(self) -> None:
        """When trial has no cost record, advisor stats are 0."""
        trial = make_trial_record(trial_id="no-cost")
        obs = EvolutionObservation(
            trial=trial,
            enrichment=ObservationEnrichment(trace_digest=None),
            workspace_version="evo-1",
            discipline="electrical",
        )

        outcome = extract_trial_outcome(obs)

        assert outcome.advisor_calls == 0
        assert outcome.advisor_input_tokens == 0
        assert outcome.advisor_output_tokens == 0


# ---------------------------------------------------------------------------
# Tests: persist and load round-trip
# ---------------------------------------------------------------------------


class TestPersistAndLoad:
    def test_persist_creates_jsonl_file(self, tmp_path: Path) -> None:
        observations = [
            _make_observation(trial_id="t1", reward=1.0),
            _make_observation(trial_id="t2", reward=0.0),
        ]

        path = persist_cycle_trials(tmp_path, cycle=1, run_id="run-01", observations=observations)

        assert path.exists()
        assert path.name == "cycle_001.jsonl"
        lines = path.read_text().strip().split("\n")
        assert len(lines) == 2

    def test_round_trip_preserves_data(self, tmp_path: Path) -> None:
        observations = [
            _make_observation(trial_id="t1", task_id="elec/vd/a", reward=1.0),
            _make_observation(trial_id="t2", task_id="elec/vd/b", reward=0.0),
        ]

        persist_cycle_trials(tmp_path, cycle=1, run_id="run-01", observations=observations)
        loaded = load_cycle_trials(tmp_path, run_id="run-01")

        assert 1 in loaded
        assert len(loaded[1]) == 2
        assert loaded[1][0].trial_id == "t1"
        assert loaded[1][0].reward == 1.0
        assert loaded[1][1].trial_id == "t2"
        assert loaded[1][1].reward == 0.0

    def test_multiple_cycles(self, tmp_path: Path) -> None:
        obs1 = [_make_observation(trial_id="c1-t1", reward=0.5)]
        obs2 = [_make_observation(trial_id="c2-t1", reward=0.8)]

        persist_cycle_trials(tmp_path, cycle=1, run_id="run-01", observations=obs1)
        persist_cycle_trials(tmp_path, cycle=2, run_id="run-01", observations=obs2)

        loaded = load_cycle_trials(tmp_path, run_id="run-01")

        assert len(loaded) == 2
        assert loaded[1][0].reward == 0.5
        assert loaded[2][0].reward == 0.8

    def test_load_latest_run_when_no_run_id(self, tmp_path: Path) -> None:
        obs_old = [_make_observation(trial_id="old", reward=0.3)]
        obs_new = [_make_observation(trial_id="new", reward=0.9)]

        persist_cycle_trials(tmp_path, cycle=1, run_id="20260410-0800", observations=obs_old)
        persist_cycle_trials(tmp_path, cycle=1, run_id="20260411-0900", observations=obs_new)

        loaded = load_cycle_trials(tmp_path)

        assert loaded[1][0].trial_id == "new"

    def test_load_empty_workspace(self, tmp_path: Path) -> None:
        loaded = load_cycle_trials(tmp_path)
        assert loaded == {}

    def test_field_scores_round_trip(self, tmp_path: Path) -> None:
        observations = [
            _make_observation(
                field_scores=[
                    FieldScore(field_name="vc_mv_per_a_m", reward=1.0),
                    FieldScore(field_name="voltage_drop_v", reward=0.0),
                    FieldScore(field_name="compliant", reward=1.0),
                ]
            ),
        ]

        persist_cycle_trials(tmp_path, cycle=1, run_id="run-01", observations=observations)
        loaded = load_cycle_trials(tmp_path, run_id="run-01")

        assert loaded[1][0].field_scores == {
            "vc_mv_per_a_m": 1.0,
            "voltage_drop_v": 0.0,
            "compliant": 1.0,
        }
