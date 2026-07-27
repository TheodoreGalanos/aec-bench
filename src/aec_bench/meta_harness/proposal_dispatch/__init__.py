# ABOUTME: Exposes the canonical governed proposal-dispatch contracts and transactions.
# ABOUTME: Keeps the package API identical to the stable proposal_dispatch_governance facade.

from aec_bench.meta_harness.proposal_dispatch.authorization import (
    authorize_governed_proposal_dispatch,
)
from aec_bench.meta_harness.proposal_dispatch.contracts import (
    GovernedProposalDispatch,
    GovernedProposalDispatchAuthorization,
    ProposalDispatchGovernanceError,
)
from aec_bench.meta_harness.proposal_dispatch.replay import (
    replay_governed_proposal_dispatch,
)

__all__ = [
    "GovernedProposalDispatch",
    "GovernedProposalDispatchAuthorization",
    "ProposalDispatchGovernanceError",
    "authorize_governed_proposal_dispatch",
    "replay_governed_proposal_dispatch",
]
