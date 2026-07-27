# ABOUTME: Preserves the historical governed proposal trial-import module surface.
# ABOUTME: Delegates all behavior to the focused proposal_trial_importing package.

from __future__ import annotations

from pathlib import Path

from aec_bench.meta_harness.authority_ledger import AuthorityLedger
from aec_bench.meta_harness.proposal_dispatch_governance import (
    GovernedProposalDispatchAuthorization,
)
from aec_bench.meta_harness.proposal_import_consumption import (
    persist_proposal_import_terminal,
)
from aec_bench.meta_harness.proposal_trial_importing import finalization as _finalization
from aec_bench.meta_harness.proposal_trial_importing import persistence as _persistence
from aec_bench.meta_harness.proposal_trial_importing import validation as _validation
from aec_bench.meta_harness.proposal_trial_importing.authority import (
    record_import_authority as _record_import_authority,
)
from aec_bench.meta_harness.proposal_trial_importing.candidate_failure import (
    replay_governed_proposal_candidate_failure_import,
)
from aec_bench.meta_harness.proposal_trial_importing.contracts import (
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
from aec_bench.meta_harness.proposal_trial_importing.replay import (
    replay_governed_proposal_trial_import,
)

_open_host_artifacts_repository = _persistence.open_host_artifacts_repository
_persist_model_path = _persistence.persist_model_path
_prepare_host_artifacts_repository = _persistence.prepare_host_artifacts_repository
_snapshot_file = _persistence.snapshot_file
_write_or_load_exact_trial_record = _persistence.write_or_load_exact_trial_record
_meta_split = _validation.meta_split
_sole_trial_dir = _validation.sole_trial_dir
_validate_exact_evidence = _validation.validate_exact_evidence

__all__ = [
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


def finalize_governed_proposal_trial_import(
    *,
    ledger: AuthorityLedger,
    authorization: GovernedProposalDispatchAuthorization,
    harbor_execution_receipt_path: Path,
    repo_root: Path,
    artifacts_root: Path,
    import_id: str,
    authority_event_id: str,
) -> ProposalTrialImportResult:
    """Finalize through the package while retaining facade patch points."""
    return _finalization.finalize_governed_proposal_trial_import(
        ledger=ledger,
        authorization=authorization,
        harbor_execution_receipt_path=harbor_execution_receipt_path,
        repo_root=repo_root,
        artifacts_root=artifacts_root,
        import_id=import_id,
        authority_event_id=authority_event_id,
        services=_finalization.FinalizationServices(
            record_authority=_record_import_authority,
            persist_terminal=persist_proposal_import_terminal,
        ),
    )
