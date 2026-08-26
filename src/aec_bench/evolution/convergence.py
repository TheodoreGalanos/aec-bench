# ABOUTME: Pure convergence checks for the functional evolution run state.
# ABOUTME: Uses the explicit score projection and configured stagnation policy without hidden engine state.

from __future__ import annotations

from aec_bench.contracts.evolution import EvolutionConfig
from aec_bench.evolution.core import EvolutionState


def is_converged(state: EvolutionState, config: EvolutionConfig) -> bool:
    """Return whether the explicit state meets the configured flat-score window."""
    window = config.stagnation_window
    if len(state.best_score_history) < window + 1:
        return False
    recent = state.best_score_history[-window:]
    return max(recent) - min(recent) <= config.improvement_threshold


__all__ = ("is_converged",)
