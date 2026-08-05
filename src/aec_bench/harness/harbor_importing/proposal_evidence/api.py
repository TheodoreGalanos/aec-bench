# ABOUTME: Owns the current Harbor proposal-evidence readers.
# ABOUTME: Selects completed or candidate-failure evidence without compatibility dispatch.

from __future__ import annotations

from pathlib import Path

from aec_bench.contracts.proposal_execution import ProposalSessionStatus
from aec_bench.harness.harbor_importing.contracts import (
    HarborImportError,
    ImportEvidenceContext,
    ImportEvidenceIntent,
    execution_kind_from_context,
)

from .contracts import PROPOSAL_EXECUTION_KIND, ProposalHarborImportEvidence
from .orchestration import load_proposal_import_evidence


def load_proposal_import_evidence_for_context(
    *,
    context: ImportEvidenceContext,
    intent: ImportEvidenceIntent,
) -> ProposalHarborImportEvidence:
    """Load proposal evidence after concrete execution-kind selection."""

    return load_proposal_import_evidence(
        context=context,
        required_status=_required_status(intent),
    )


def load_proposal_harbor_import_evidence(
    *,
    trial_dir: Path,
    repo_root: Path,
) -> ProposalHarborImportEvidence | None:
    """Load completed proposal evidence without constructing a TrialRecord."""

    return _load_public_proposal_evidence(
        trial_dir=trial_dir,
        repo_root=repo_root,
        intent=ImportEvidenceIntent.TRIAL_RECORD,
    )


def load_proposal_harbor_candidate_failure_evidence(
    *,
    trial_dir: Path,
    repo_root: Path,
) -> ProposalHarborImportEvidence | None:
    """Load reconciled proposal candidate-failure evidence without a TrialRecord."""

    return _load_public_proposal_evidence(
        trial_dir=trial_dir,
        repo_root=repo_root,
        intent=ImportEvidenceIntent.CANDIDATE_FAILURE,
    )


def _load_public_proposal_evidence(
    *,
    trial_dir: Path,
    repo_root: Path,
    intent: ImportEvidenceIntent,
) -> ProposalHarborImportEvidence | None:
    from aec_bench.harness.harbor_importing.core import (
        build_import_evidence_context,
    )

    context = build_import_evidence_context(
        trial_dir=Path(trial_dir),
        repo_root=Path(repo_root),
    )
    if execution_kind_from_context(context) != PROPOSAL_EXECUTION_KIND:
        return None
    return load_proposal_import_evidence_for_context(
        context=context,
        intent=intent,
    )


def _required_status(
    intent: ImportEvidenceIntent,
) -> ProposalSessionStatus:
    if intent is ImportEvidenceIntent.TRIAL_RECORD:
        return ProposalSessionStatus.COMPLETED
    if intent is ImportEvidenceIntent.CANDIDATE_FAILURE:
        return ProposalSessionStatus.CANDIDATE_FAILURE
    raise HarborImportError(
        f"unsupported proposal import evidence intent: {intent}",
    )
