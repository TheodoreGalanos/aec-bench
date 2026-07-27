# ABOUTME: Preserves the stable import surface for governed proposal dispatch.
# ABOUTME: Delegates contract and transaction ownership to the cohesive proposal_dispatch package.

from aec_bench.meta_harness.proposal_dispatch import (
    GovernedProposalDispatch,
    GovernedProposalDispatchAuthorization,
    ProposalDispatchGovernanceError,
    authorize_governed_proposal_dispatch,
    replay_governed_proposal_dispatch,
)

__all__ = [
    "GovernedProposalDispatch",
    "GovernedProposalDispatchAuthorization",
    "ProposalDispatchGovernanceError",
    "authorize_governed_proposal_dispatch",
    "replay_governed_proposal_dispatch",
]
