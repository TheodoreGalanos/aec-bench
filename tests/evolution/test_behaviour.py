# ABOUTME: Tests for BehaviourDescriptor extraction from EvolutionObservations.
# ABOUTME: Covers all BD vector dimensions: token cost, bond ratios, tool density, reward passthrough.

import pytest

from aec_bench.contracts.evolution import (
    BehaviourDescriptor,
    EvolutionObservation,
    ObservationEnrichment,
    TraceDigest,
)
from aec_bench.contracts.trial_record import CostRecord
from tests.support.trial_record_factories import make_trial_record

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_obs(
    bond_sequence: str = "E-E-V-D-X",
    turn_count: int = 5,
    tool_call_count: int = 3,
    reward: float = 0.8,
    tokens_in: int | None = 1000,
    tokens_out: int | None = 500,
    trace_digest: TraceDigest | None = None,
    include_cost: bool = True,
) -> EvolutionObservation:
    """Build a minimal but valid EvolutionObservation for testing."""
    record = make_trial_record(
        evaluation={
            "reward": reward,
            "validity": {
                "output_parseable": True,
                "schema_valid": True,
                "verifier_completed": True,
            },
        },
        cost=CostRecord(tokens_in=tokens_in, tokens_out=tokens_out) if include_cost else None,
    )

    if trace_digest is None:
        digest = TraceDigest(
            turn_count=turn_count,
            tool_call_count=tool_call_count,
            tool_error_count=0,
            bond_sequence=bond_sequence,
        )
    else:
        digest = trace_digest

    return EvolutionObservation(
        trial=record,
        enrichment=ObservationEnrichment(trace_digest=digest),
        workspace_version="evo-1",
        discipline="electrical",
    )


# ---------------------------------------------------------------------------
# TestTokenCost
# ---------------------------------------------------------------------------


class TestTokenCost:
    def test_token_cost_is_sum_of_tokens_in_and_out(self) -> None:
        from aec_bench.evolution.behaviour import extract_behaviour_descriptor

        obs = _make_obs(tokens_in=1000, tokens_out=500)
        bd = extract_behaviour_descriptor(obs)

        assert bd.token_cost == 1500.0

    def test_missing_cost_gives_zero(self) -> None:
        from aec_bench.evolution.behaviour import extract_behaviour_descriptor

        obs = _make_obs(include_cost=False)
        bd = extract_behaviour_descriptor(obs)

        assert bd.token_cost == 0.0

    def test_none_token_values_treated_as_zero(self) -> None:
        from aec_bench.evolution.behaviour import extract_behaviour_descriptor

        obs = _make_obs(tokens_in=None, tokens_out=None)
        bd = extract_behaviour_descriptor(obs)

        assert bd.token_cost == 0.0


# ---------------------------------------------------------------------------
# TestVerificationDepth
# ---------------------------------------------------------------------------


class TestVerificationDepth:
    def test_verification_depth_from_bond_sequence(self) -> None:
        from aec_bench.evolution.behaviour import extract_behaviour_descriptor

        # "E-E-V-D-X" → V_count=1, length=5 → 1/5 = 0.2
        obs = _make_obs(bond_sequence="E-E-V-D-X", turn_count=5)
        bd = extract_behaviour_descriptor(obs)

        assert bd.verification_depth == pytest.approx(0.2)

    def test_all_v_sequence_gives_verification_depth_one(self) -> None:
        from aec_bench.evolution.behaviour import extract_behaviour_descriptor

        obs = _make_obs(bond_sequence="V-V-V-V", turn_count=4)
        bd = extract_behaviour_descriptor(obs)

        assert bd.verification_depth == pytest.approx(1.0)

    def test_no_v_bonds_gives_zero_verification_depth(self) -> None:
        from aec_bench.evolution.behaviour import extract_behaviour_descriptor

        obs = _make_obs(bond_sequence="E-E-E", turn_count=3)
        bd = extract_behaviour_descriptor(obs)

        assert bd.verification_depth == 0.0


# ---------------------------------------------------------------------------
# TestToolDensity
# ---------------------------------------------------------------------------


class TestToolDensity:
    def test_tool_density_is_tool_calls_over_turns(self) -> None:
        from aec_bench.evolution.behaviour import extract_behaviour_descriptor

        obs = _make_obs(bond_sequence="E-E-E", turn_count=3, tool_call_count=9)
        bd = extract_behaviour_descriptor(obs)

        assert bd.tool_density == pytest.approx(3.0)

    def test_tool_density_zero_when_no_turns(self) -> None:
        from aec_bench.evolution.behaviour import extract_behaviour_descriptor

        digest = TraceDigest(
            turn_count=0,
            tool_call_count=0,
            tool_error_count=0,
            bond_sequence="",
        )
        obs = _make_obs(trace_digest=digest)
        bd = extract_behaviour_descriptor(obs)

        assert bd.tool_density == 0.0


# ---------------------------------------------------------------------------
# TestExplorationRatio
# ---------------------------------------------------------------------------


class TestExplorationRatio:
    def test_exploration_ratio_from_bond_sequence(self) -> None:
        from aec_bench.evolution.behaviour import extract_behaviour_descriptor

        # "E-E-V-D-X" → X_count=1, length=5 → 1/5 = 0.2
        obs = _make_obs(bond_sequence="E-E-V-D-X", turn_count=5)
        bd = extract_behaviour_descriptor(obs)

        assert bd.exploration_ratio == pytest.approx(0.2)

    def test_multiple_x_bonds(self) -> None:
        from aec_bench.evolution.behaviour import extract_behaviour_descriptor

        obs = _make_obs(bond_sequence="X-X-E-X", turn_count=4)
        bd = extract_behaviour_descriptor(obs)

        assert bd.exploration_ratio == pytest.approx(0.75)


# ---------------------------------------------------------------------------
# TestDeliberationRatio
# ---------------------------------------------------------------------------


class TestDeliberationRatio:
    def test_deliberation_ratio_from_bond_sequence(self) -> None:
        from aec_bench.evolution.behaviour import extract_behaviour_descriptor

        # "E-E-V-D-X" → D_count=1, length=5 → 1/5 = 0.2
        obs = _make_obs(bond_sequence="E-E-V-D-X", turn_count=5)
        bd = extract_behaviour_descriptor(obs)

        assert bd.deliberation_ratio == pytest.approx(0.2)

    def test_multiple_d_bonds(self) -> None:
        from aec_bench.evolution.behaviour import extract_behaviour_descriptor

        obs = _make_obs(bond_sequence="D-D-D-E", turn_count=4)
        bd = extract_behaviour_descriptor(obs)

        assert bd.deliberation_ratio == pytest.approx(0.75)


# ---------------------------------------------------------------------------
# TestRewardPassthrough
# ---------------------------------------------------------------------------


class TestRewardPassthrough:
    def test_reward_passthrough(self) -> None:
        from aec_bench.evolution.behaviour import extract_behaviour_descriptor

        obs = _make_obs(reward=0.65)
        bd = extract_behaviour_descriptor(obs)

        assert bd.reward == pytest.approx(0.65)

    def test_reward_zero(self) -> None:
        from aec_bench.evolution.behaviour import extract_behaviour_descriptor

        obs = _make_obs(reward=0.0)
        bd = extract_behaviour_descriptor(obs)

        assert bd.reward == 0.0


# ---------------------------------------------------------------------------
# TestMissingTraceDigest
# ---------------------------------------------------------------------------


class TestMissingTraceDigest:
    def test_missing_trace_digest_gives_zero_ratios(self) -> None:
        from aec_bench.evolution.behaviour import extract_behaviour_descriptor

        record = make_trial_record(
            evaluation={
                "reward": 0.5,
                "validity": {
                    "output_parseable": True,
                    "schema_valid": True,
                    "verifier_completed": True,
                },
            },
        )
        obs = EvolutionObservation(
            trial=record,
            enrichment=ObservationEnrichment(trace_digest=None),
            workspace_version="evo-1",
            discipline="electrical",
        )

        bd = extract_behaviour_descriptor(obs)

        assert bd.verification_depth == 0.0
        assert bd.exploration_ratio == 0.0
        assert bd.deliberation_ratio == 0.0
        assert bd.tool_density == 0.0


# ---------------------------------------------------------------------------
# TestBDIsFrozen
# ---------------------------------------------------------------------------


class TestBDIsFrozen:
    def test_bd_is_frozen(self) -> None:
        from aec_bench.evolution.behaviour import extract_behaviour_descriptor

        obs = _make_obs()
        bd = extract_behaviour_descriptor(obs)

        assert isinstance(bd, BehaviourDescriptor)
        with pytest.raises((TypeError, Exception)):
            bd.token_cost = 9999.0  # type: ignore[misc]
