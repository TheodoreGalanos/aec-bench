# ABOUTME: Evolution domain for aec-bench — automated agent improvement.
# ABOUTME: Provides workspace management, behavioral analysis, and evolution engine.

from aec_bench.evolution.application import (
    ReportWriter,
    run_evolution,
    run_evolution_from_config,
)
from aec_bench.evolution.backends.local import build_local_checks
from aec_bench.evolution.core import (
    CandidateProposal,
    CandidateProposalRequest,
    ProposalStatus,
    gate_candidate,
    next_evolution_state,
)
from aec_bench.evolution.evaluation import CandidateChecks
from aec_bench.evolution.proposer import build_avo

__all__ = (
    "CandidateChecks",
    "CandidateProposal",
    "CandidateProposalRequest",
    "ProposalStatus",
    "ReportWriter",
    "build_avo",
    "build_local_checks",
    "gate_candidate",
    "next_evolution_state",
    "run_evolution",
    "run_evolution_from_config",
)
