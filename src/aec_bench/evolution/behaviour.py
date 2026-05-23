# ABOUTME: Behaviour descriptor extraction from evolution observations.
# ABOUTME: Maps TraceDigest bond sequences and CostRecord to a BD vector for MAP-Elites.

from __future__ import annotations

from aec_bench.contracts.evolution import BehaviourDescriptor, EvolutionObservation


def extract_behaviour_descriptor(obs: EvolutionObservation) -> BehaviourDescriptor:
    """Extract a BehaviourDescriptor vector from an EvolutionObservation.

    Computes token cost from the trial's CostRecord, parses bond counts from the
    trace digest's bond_sequence, and derives tool density from tool_call_count
    and turn_count. All ratio fields default to 0.0 when the underlying data is
    absent or sequence length is zero.
    """
    cost = obs.trial.cost
    if cost is not None:
        token_cost = float((cost.tokens_in or 0) + (cost.tokens_out or 0))
    else:
        token_cost = 0.0

    reward = obs.trial.evaluation.reward

    trace_digest = obs.enrichment.trace_digest
    if trace_digest is None or not trace_digest.bond_sequence:
        return BehaviourDescriptor(
            token_cost=token_cost,
            verification_depth=0.0,
            tool_density=0.0,
            exploration_ratio=0.0,
            deliberation_ratio=0.0,
            reward=reward,
        )

    bonds = trace_digest.bond_sequence.split("-")
    sequence_length = len(bonds)

    v_count = bonds.count("V")
    x_count = bonds.count("X")
    d_count = bonds.count("D")

    verification_depth = v_count / sequence_length
    exploration_ratio = x_count / sequence_length
    deliberation_ratio = d_count / sequence_length

    turn_count = trace_digest.turn_count
    if turn_count > 0:
        tool_density = trace_digest.tool_call_count / turn_count
    else:
        tool_density = 0.0

    return BehaviourDescriptor(
        token_cost=token_cost,
        verification_depth=verification_depth,
        tool_density=tool_density,
        exploration_ratio=exploration_ratio,
        deliberation_ratio=deliberation_ratio,
        reward=reward,
    )
