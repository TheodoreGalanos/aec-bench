# ABOUTME: Exposes the canonical governed proposal trial-import API.
# ABOUTME: Keeps contracts, finalization, replay, and candidate failures independently testable.

from aec_bench.experimentation.proposals.proposal_trial_importing.candidate_failure import (
    replay_governed_proposal_candidate_failure_import,
)
from aec_bench.experimentation.proposals.proposal_trial_importing.contracts import (
    GovernedProposalCandidateFailureImport,
    GovernedProposalTrialImport,
    ProposalCandidateFailureRecord,
    ProposalNodeImportAuthority,
    ProposalTrialImportAuthority,
    ProposalTrialImportError,
    ProposalTrialImportReceipt,
    ProposalTrialImportResult,
    ProposalVerifierEvidence,
)
from aec_bench.experimentation.proposals.proposal_trial_importing.finalization import (
    FinalizationServices,
    finalize_governed_proposal_trial_import,
)
from aec_bench.experimentation.proposals.proposal_trial_importing.replay import (
    replay_governed_proposal_trial_import,
)

__all__ = [
    "FinalizationServices",
    "GovernedProposalCandidateFailureImport",
    "GovernedProposalTrialImport",
    "ProposalCandidateFailureRecord",
    "ProposalNodeImportAuthority",
    "ProposalTrialImportAuthority",
    "ProposalTrialImportError",
    "ProposalTrialImportReceipt",
    "ProposalTrialImportResult",
    "ProposalVerifierEvidence",
    "finalize_governed_proposal_trial_import",
    "replay_governed_proposal_candidate_failure_import",
    "replay_governed_proposal_trial_import",
]
