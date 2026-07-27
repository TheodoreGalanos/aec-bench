# ABOUTME: Preserves the stable import surface for exact governed proposal freezing.
# ABOUTME: Delegates contract, issuance, evidence, validation, and replay ownership to proposal_freezing.

from aec_bench.meta_harness.proposal_freezing import (
    GovernedProposalFreezeError,
    GovernedProposalFreezeResult,
    IncumbentArtifact,
    ProposalArtifact,
    ProposalFreezeBasis,
    ProposalFreezeLifecyclePolicy,
    assert_proposal_freeze_authority,
    issue_governed_proposal_freeze,
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
