# ABOUTME: Exposes canonical proposal-freeze contracts, issuance, and replay transactions.
# ABOUTME: Keeps the package API identical to the stable proposal_freeze compatibility facade.

from aec_bench.meta_harness.proposal_freezing.contracts import (
    GovernedProposalFreezeError,
    GovernedProposalFreezeResult,
    IncumbentArtifact,
    ProposalArtifact,
    ProposalFreezeBasis,
)
from aec_bench.meta_harness.proposal_freezing.issuance import (
    issue_governed_proposal_freeze,
)
from aec_bench.meta_harness.proposal_freezing.replay import (
    assert_proposal_freeze_authority,
)
from aec_bench.meta_harness.proposal_freezing.validation import (
    ProposalFreezeLifecyclePolicy,
)

__all__ = [
    "GovernedProposalFreezeError",
    "GovernedProposalFreezeResult",
    "IncumbentArtifact",
    "ProposalArtifact",
    "ProposalFreezeBasis",
    "ProposalFreezeLifecyclePolicy",
    "assert_proposal_freeze_authority",
    "issue_governed_proposal_freeze",
]
