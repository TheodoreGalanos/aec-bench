# ABOUTME: Owns the public Harbor proposal-import extension and compatibility loaders.
# ABOUTME: Selects completed or candidate-failure evidence without leaking host paths.

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from aec_bench.contracts.proposal_execution import ProposalSessionStatus
from aec_bench.harness.harbor_importing.contracts import (
    HarborImportError,
    ImportEvidenceContext,
    ImportEvidenceIntent,
)
from aec_bench.harness.harbor_importing.registry import execution_kind_from_context

from .contracts import PROPOSAL_EXECUTION_KIND, ProposalHarborImportEvidence
from .orchestration import load_proposal_import_evidence


@dataclass(frozen=True)
class ProposalImportEvidenceExtension:
    """Load proposal evidence after the generic importer selects its kind."""

    execution_kind: str = PROPOSAL_EXECUTION_KIND

    def load(
        self,
        *,
        context: ImportEvidenceContext,
        intent: ImportEvidenceIntent,
    ) -> ProposalHarborImportEvidence:
        return load_proposal_import_evidence(
            context=context,
            required_status=_required_status(intent),
        )


PROPOSAL_IMPORT_EVIDENCE_EXTENSION = ProposalImportEvidenceExtension()


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
    return PROPOSAL_IMPORT_EVIDENCE_EXTENSION.load(
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


__all__ = (
    "PROPOSAL_IMPORT_EVIDENCE_EXTENSION",
    "ProposalImportEvidenceExtension",
    "load_proposal_harbor_candidate_failure_evidence",
    "load_proposal_harbor_import_evidence",
)
