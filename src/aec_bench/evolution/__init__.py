# ABOUTME: Evolution domain for aec-bench — automated agent improvement.
# ABOUTME: Provides workspace management, behavioral analysis, and evolution engine.

from aec_bench.evolution.application import (
    CandidateEvaluator,
    ReportWriter,
    run_evolution,
    run_evolution_from_config,
)

__all__ = (
    "CandidateEvaluator",
    "ReportWriter",
    "run_evolution",
    "run_evolution_from_config",
)
