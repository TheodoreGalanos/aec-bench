# ABOUTME: Defines Harbor proposal-import evidence and its sealed boundary contracts.
# ABOUTME: Keeps portable public provenance separate from host-only reconciliation state.

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from aec_bench.contracts.evaluation_result import EvaluationResult
from aec_bench.contracts.proposal_execution import ProposalSessionReceipt
from aec_bench.contracts.trial_record import ArtifactReference

PROPOSAL_EXECUTION_KIND = "proposal_session"


@dataclass(frozen=True)
class ProposalHarborImportEvidence:
    """Verified proposal-session evidence sufficient for later provenance assembly."""

    session_id: str
    candidate_id: str
    candidate_artifact_sha256: str
    proposal_graph_sha256: str
    compilation_sha256: str
    session_plan_sha256: str
    session_receipt: ProposalSessionReceipt
    session_receipt_artifact: ArtifactReference
    cleanup_receipt_artifact: ArtifactReference
    task_package_manifest_artifact: ArtifactReference
    runtime_archive_artifact: ArtifactReference
    artifacts: tuple[ArtifactReference, ...]

    @property
    def execution_kind(self) -> str:
        """Return the execution kind used to select this extension."""

        return PROPOSAL_EXECUTION_KIND

    @property
    def adapter_name(self) -> str:
        """Return the stable TrialRecord adapter identity."""

        return PROPOSAL_EXECUTION_KIND

    def sanitize_agent_configuration(
        self,
        configuration: dict[str, Any],
    ) -> dict[str, Any]:
        """Replace host-only proposal paths with verified content identities."""

        portable = dict(configuration)
        portable.pop("proposal_session", None)
        portable.pop("extra_env", None)
        portable["proposal_session"] = {
            "session_id": self.session_id,
            "candidate_id": self.candidate_id,
            "candidate_artifact_sha256": self.candidate_artifact_sha256,
            "proposal_graph_sha256": self.proposal_graph_sha256,
            "compilation_sha256": self.compilation_sha256,
            "session_plan_sha256": self.session_plan_sha256,
            "session_receipt_sha256": self.session_receipt.content_sha256,
        }
        return portable

    def augment_evaluation(
        self,
        evaluation: EvaluationResult,
    ) -> EvaluationResult:
        """Keep proposal-session evaluation unchanged."""

        return evaluation

    @property
    def episode_artifact(self) -> ArtifactReference | None:
        """Proposal sessions do not produce a task-owned episode artifact."""

        return None


class ProposalCleanupReceipt(Protocol):
    """Provider-owned cleanup evidence consumed through a typed import boundary."""

    receipt_path: Path
    receipt_sha256: str
    content_sha256: str
    runtime_archive_sha256: str
    runtime_archive_content_sha256: str
    runtime_snapshot_identity: str
    trial_instance_identity: str
    rotation_receipt_sha256: str
    rotation_receipt_content_sha256: str
    verifier_container_identity: str
    handoff_variant: str
    candidate_failure_session_receipt_sha256: str | None


@dataclass(frozen=True)
class ProposalSealedArtifact:
    """One content-addressed artifact inside the provider boundary."""

    remote_path: str
    path: Path
    sha256: str
    size_bytes: int


@dataclass(frozen=True)
class ProposalBoundaryEvidence:
    """Reconciled cleanup, rotation, seal, and sealed-artifact evidence."""

    cleanup: ProposalCleanupReceipt
    rotation_path: Path
    seal_path: Path
    sealed_artifacts: tuple[ProposalSealedArtifact, ...]


__all__ = ("ProposalHarborImportEvidence",)
