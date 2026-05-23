# ABOUTME: Tests for evolution analysis functions — per-field, per-discipline, and bond deviation.
# ABOUTME: Covers pattern detection and graduated scope computation.

from aec_bench.contracts.evolution import (
    DisciplineScore,
    EvolutionObservation,
    FieldScore,
    ObservationEnrichment,
    TraceDigest,
)
from aec_bench.evolution.analysis import (
    GraduatedScope,
    compute_discipline_scores,
    compute_graduated_scope,
    detect_behavioral_patterns,
)
from tests.support.trial_record_factories import make_trial_record

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_observation(
    discipline: str = "electrical",
    reward: float = 0.8,
    field_scores: list[FieldScore] | None = None,
    bond_sequence: str = "E-D-E-V",
) -> EvolutionObservation:
    record = make_trial_record(
        evaluation={
            "reward": reward,
            "validity": {
                "output_parseable": True,
                "schema_valid": True,
                "verifier_completed": True,
            },
        },
    )
    return EvolutionObservation(
        trial=record,
        enrichment=ObservationEnrichment(
            field_scores=field_scores or [],
            trace_digest=TraceDigest(
                turn_count=4,
                tool_call_count=3,
                tool_error_count=0,
                bond_sequence=bond_sequence,
            ),
        ),
        workspace_version="evo-1",
        discipline=discipline,
    )


# ---------------------------------------------------------------------------
# TestComputeDisciplineScores
# ---------------------------------------------------------------------------


class TestComputeDisciplineScores:
    def test_single_discipline(self) -> None:
        obs1 = _make_observation(
            discipline="electrical",
            reward=0.8,
            field_scores=[
                FieldScore(field_name="v_drop", reward=1.0),
                FieldScore(field_name="compliance", reward=0.0),
            ],
        )
        obs2 = _make_observation(
            discipline="electrical",
            reward=1.0,
            field_scores=[
                FieldScore(field_name="v_drop", reward=1.0),
                FieldScore(field_name="compliance", reward=1.0),
            ],
        )

        result = compute_discipline_scores([obs1, obs2])

        assert len(result) == 1
        score = result[0]
        assert isinstance(score, DisciplineScore)
        assert score.discipline == "electrical"
        assert score.task_count == 2
        assert abs(score.mean_reward - 0.9) < 1e-9
        # 3 out of 4 field_scores have reward >= 1.0
        assert abs(score.field_pass_rate - 0.75) < 1e-9
        assert score.mean_structural_similarity is None

    def test_multi_discipline(self) -> None:
        obs_electrical = _make_observation(discipline="electrical", reward=0.9)
        obs_civil_1 = _make_observation(discipline="civil", reward=0.7)
        obs_civil_2 = _make_observation(discipline="civil", reward=0.8)

        result = compute_discipline_scores([obs_electrical, obs_civil_1, obs_civil_2])

        assert len(result) == 2
        disciplines = {s.discipline for s in result}
        assert disciplines == {"electrical", "civil"}

        civil_score = next(s for s in result if s.discipline == "civil")
        assert civil_score.task_count == 2

        electrical_score = next(s for s in result if s.discipline == "electrical")
        assert electrical_score.task_count == 1

    def test_sorted_by_discipline_name(self) -> None:
        obs_z = _make_observation(discipline="structural", reward=0.8)
        obs_a = _make_observation(discipline="civil", reward=0.9)

        result = compute_discipline_scores([obs_z, obs_a])

        assert result[0].discipline == "civil"
        assert result[1].discipline == "structural"

    def test_no_field_scores_gives_zero_pass_rate(self) -> None:
        obs = _make_observation(discipline="mechanical", reward=0.7, field_scores=[])

        result = compute_discipline_scores([obs])

        assert result[0].field_pass_rate == 0.0

    def test_empty_observations_returns_empty(self) -> None:
        result = compute_discipline_scores([])
        assert result == []


# ---------------------------------------------------------------------------
# TestDetectBehavioralPatterns
# ---------------------------------------------------------------------------


class TestDetectBehavioralPatterns:
    def test_detects_blind_action(self) -> None:
        obs1 = _make_observation(
            reward=0.5,
            bond_sequence="E-E-E-E-E-E",
        )
        obs2 = _make_observation(
            reward=0.6,
            bond_sequence="E-E-E-E-E",
        )

        result = detect_behavioral_patterns([obs1, obs2])

        names = {p.name for p in result}
        assert "blind_action" in names
        blind = next(p for p in result if p.name == "blind_action")
        assert blind.count >= 2

    def test_detects_no_verification(self) -> None:
        obs1 = _make_observation(reward=0.5, bond_sequence="E-D-E-D-E")
        obs2 = _make_observation(reward=0.6, bond_sequence="E-E-D-E")
        obs3 = _make_observation(reward=0.4, bond_sequence="X-D-E")

        result = detect_behavioral_patterns([obs1, obs2, obs3])

        names = {p.name for p in result}
        assert "no_verification" in names
        no_v = next(p for p in result if p.name == "no_verification")
        assert no_v.count >= 3

    def test_no_patterns_in_good_traces(self) -> None:
        # reward = 0.95 means trial is not "failed" (< 0.8)
        obs = _make_observation(reward=0.95, bond_sequence="E-D-E-V")

        result = detect_behavioral_patterns([obs])

        assert result == []

    def test_detects_analysis_paralysis(self) -> None:
        # 3+ consecutive X or D bonds without E
        obs1 = _make_observation(reward=0.5, bond_sequence="D-D-D-E-V")
        obs2 = _make_observation(reward=0.6, bond_sequence="X-X-X-E-V")

        result = detect_behavioral_patterns([obs1, obs2])

        names = {p.name for p in result}
        assert "analysis_paralysis" in names
        paralysis = next(p for p in result if p.name == "analysis_paralysis")
        assert paralysis.count >= 2

    def test_min_count_threshold(self) -> None:
        # Only one blind_action observation — below min_count=2
        obs = _make_observation(reward=0.5, bond_sequence="E-E-E-E-E-E")

        result = detect_behavioral_patterns([obs], min_count=2)

        names = {p.name for p in result}
        assert "blind_action" not in names

    def test_skips_observations_without_trace_digest(self) -> None:
        record = make_trial_record(
            evaluation={
                "reward": 0.3,
                "validity": {
                    "output_parseable": True,
                    "schema_valid": True,
                    "verifier_completed": True,
                },
            }
        )
        obs_no_digest = EvolutionObservation(
            trial=record,
            enrichment=ObservationEnrichment(field_scores=[], trace_digest=None),
            workspace_version="evo-1",
            discipline="electrical",
        )

        # Should not raise even though trace_digest is None
        result = detect_behavioral_patterns([obs_no_digest])
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# TestNewBehavioralPatterns
# ---------------------------------------------------------------------------


class TestNewBehavioralPatterns:
    def test_detects_redundant_verification(self) -> None:
        """V-V-V pattern: agent over-checks without making progress."""
        obs1 = _make_observation(reward=0.5, bond_sequence="V-V-V-V-E")
        obs2 = _make_observation(reward=0.6, bond_sequence="E-V-V-V-D")

        result = detect_behavioral_patterns([obs1, obs2])

        names = {p.name for p in result}
        assert "redundant_verification" in names
        pattern = next(p for p in result if p.name == "redundant_verification")
        assert pattern.count >= 2

    def test_detects_no_exploration(self) -> None:
        """Agent jumps straight to execution without reading the task first."""
        obs1 = _make_observation(reward=0.5, bond_sequence="E-E-E-V")
        obs2 = _make_observation(reward=0.6, bond_sequence="E-V-E-D")

        result = detect_behavioral_patterns([obs1, obs2])

        names = {p.name for p in result}
        assert "no_exploration" in names
        pattern = next(p for p in result if p.name == "no_exploration")
        assert pattern.count >= 2

    def test_no_exploration_not_triggered_when_x_present(self) -> None:
        """If X appears before the first E, no_exploration should not fire."""
        obs1 = _make_observation(reward=0.5, bond_sequence="X-D-E-E-V")
        obs2 = _make_observation(reward=0.6, bond_sequence="X-E-E-V")

        result = detect_behavioral_patterns([obs1, obs2])

        names = {p.name for p in result}
        assert "no_exploration" not in names

    def test_redundant_verification_not_triggered_for_two_v(self) -> None:
        """Two consecutive V bonds should not trigger redundant_verification (needs 3+)."""
        obs1 = _make_observation(reward=0.5, bond_sequence="V-V-E-D")
        obs2 = _make_observation(reward=0.6, bond_sequence="E-V-V-D")

        result = detect_behavioral_patterns([obs1, obs2])

        names = {p.name for p in result}
        assert "redundant_verification" not in names

    def test_no_exploration_requires_e_at_start(self) -> None:
        """Sequences that begin with D instead of E should not trigger no_exploration."""
        obs1 = _make_observation(reward=0.5, bond_sequence="D-E-V")
        obs2 = _make_observation(reward=0.6, bond_sequence="D-D-E-V")

        result = detect_behavioral_patterns([obs1, obs2])

        names = {p.name for p in result}
        assert "no_exploration" not in names


# ---------------------------------------------------------------------------
# TestComputeGraduatedScope
# ---------------------------------------------------------------------------


class TestComputeGraduatedScope:
    def test_high_score_stagnant_skips(self) -> None:
        result = compute_graduated_scope(batch_score=0.92, improving=False)
        assert result == GraduatedScope.SKIP

    def test_high_score_improving_minimal(self) -> None:
        result = compute_graduated_scope(batch_score=0.91, improving=True)
        assert result == GraduatedScope.MINIMAL

    def test_mid_score_targeted(self) -> None:
        result = compute_graduated_scope(batch_score=0.82, improving=False)
        assert result == GraduatedScope.TARGETED

    def test_mid_score_improving_targeted(self) -> None:
        result = compute_graduated_scope(batch_score=0.85, improving=True)
        assert result == GraduatedScope.TARGETED

    def test_low_score_comprehensive(self) -> None:
        result = compute_graduated_scope(batch_score=0.65, improving=False)
        assert result == GraduatedScope.COMPREHENSIVE

    def test_low_score_improving_still_comprehensive(self) -> None:
        result = compute_graduated_scope(batch_score=0.75, improving=True)
        assert result == GraduatedScope.COMPREHENSIVE

    def test_boundary_exactly_0_90_not_improving(self) -> None:
        result = compute_graduated_scope(batch_score=0.90, improving=False)
        assert result == GraduatedScope.SKIP

    def test_boundary_exactly_0_80_targeted(self) -> None:
        result = compute_graduated_scope(batch_score=0.80, improving=False)
        assert result == GraduatedScope.TARGETED
