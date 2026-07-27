# ABOUTME: Exposes the canonical Harbor proposal-import evidence implementation.
# ABOUTME: Keeps the historical proposal module as a stable identity-preserving facade.

from .api import (
    PROPOSAL_IMPORT_EVIDENCE_EXTENSION,
    ProposalImportEvidenceExtension,
    load_proposal_harbor_candidate_failure_evidence,
    load_proposal_harbor_import_evidence,
)
from .contracts import ProposalHarborImportEvidence

__all__ = (
    "PROPOSAL_IMPORT_EVIDENCE_EXTENSION",
    "ProposalHarborImportEvidence",
    "ProposalImportEvidenceExtension",
    "load_proposal_harbor_candidate_failure_evidence",
    "load_proposal_harbor_import_evidence",
)
