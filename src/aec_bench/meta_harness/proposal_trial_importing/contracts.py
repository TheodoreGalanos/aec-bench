# ABOUTME: Defines the stable contracts returned by governed proposal trial import.
# ABOUTME: Keeps scored and candidate-failure terminal results explicit and content addressed.

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from aec_bench.contracts.evaluation_result import EvaluationResult
from aec_bench.contracts.harness_kernel import ContentAddressedModel, validate_sha256
from aec_bench.contracts.proposal_execution.session import ProposalSessionReceipt
from aec_bench.contracts.proposal_execution_types import ProposalSessionStatus
from aec_bench.contracts.trial_record import ArtifactReference, TrialRecord
from aec_bench.contracts.validators import NonEmptyStr
from aec_bench.harness.harbor_importing.proposal_evidence import ProposalHarborImportEvidence
from aec_bench.meta_harness.authority_ledger import StoredAuthorityEvent, StoredBasis
from aec_bench.meta_harness.proposal_import_consumption import (
    ProposalImportConsumptionClaim,
    ProposalImportTerminalRecord,
)


class ProposalTrialImportError(ValueError):
    """Reject incomplete, drifted, or unauthorized proposal import evidence."""


class ProposalVerifierEvidence(ContentAddressedModel):
    """Exact task-authority verifier evidence used by one proposal import."""

    schema_version: Literal["aecbench.proposal-verifier-evidence.v1"] = "aecbench.proposal-verifier-evidence.v1"
    trial_id: NonEmptyStr
    task_id: NonEmptyStr
    session_id: NonEmptyStr
    reward_artifact: ArtifactReference
    details_artifact: ArtifactReference
    evaluation: EvaluationResult


class ProposalTrialImportReceipt(ContentAddressedModel):
    """Non-circular receipt binding one persisted TrialRecord to its proposal run."""

    schema_version: Literal["aecbench.proposal-trial-import-receipt.v1"] = "aecbench.proposal-trial-import-receipt.v1"
    import_id: NonEmptyStr
    dispatch_id: NonEmptyStr
    dispatch_sha256: str
    provider_dispatch_event_sha256: str
    harbor_execution_receipt_sha256: str
    trial_id: NonEmptyStr
    trial_record: ArtifactReference
    session_id: NonEmptyStr
    candidate_id: NonEmptyStr
    candidate_artifact_sha256: str
    proposal_graph_sha256: str
    compilation_sha256: str
    session_plan_sha256: str
    world_package_sha256: str
    topology_signature_sha256: str
    verifier_evidence_sha256: str
    node_receipt_sha256s: tuple[str, ...] = Field(min_length=1)

    @field_validator(
        "dispatch_sha256",
        "provider_dispatch_event_sha256",
        "harbor_execution_receipt_sha256",
        "candidate_artifact_sha256",
        "proposal_graph_sha256",
        "compilation_sha256",
        "session_plan_sha256",
        "world_package_sha256",
        "topology_signature_sha256",
        "verifier_evidence_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("node_receipt_sha256s")
    @classmethod
    def canonicalize_node_receipts(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        for digest in value:
            validate_sha256(digest)
        if len(value) != len(set(value)):
            raise ValueError("proposal import node receipt identities must be unique")
        return tuple(sorted(value))


class ProposalCandidateFailureRecord(ContentAddressedModel):
    """Preserved candidate-failure evidence that explicitly forbids a TrialRecord."""

    schema_version: Literal["aecbench.proposal-candidate-failure-import.v1"] = (
        "aecbench.proposal-candidate-failure-import.v1"
    )
    import_id: NonEmptyStr
    dispatch_id: NonEmptyStr
    dispatch_sha256: str
    harbor_execution_receipt_sha256: str
    candidate_id: NonEmptyStr
    candidate_artifact_sha256: str
    proposal_graph_sha256: str
    compilation_sha256: str
    session_plan_sha256: str
    session_receipt: ProposalSessionReceipt
    artifacts: tuple[ArtifactReference, ...] = Field(min_length=1)
    trial_record_permitted: Literal[False] = False
    scored_import_authority_permitted: Literal[False] = False

    @field_validator(
        "dispatch_sha256",
        "harbor_execution_receipt_sha256",
        "candidate_artifact_sha256",
        "proposal_graph_sha256",
        "compilation_sha256",
        "session_plan_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("artifacts")
    @classmethod
    def canonicalize_artifacts(
        cls,
        value: tuple[ArtifactReference, ...],
    ) -> tuple[ArtifactReference, ...]:
        identities = tuple((item.kind, item.path, item.sha256) for item in value)
        if len(identities) != len(set(identities)):
            raise ValueError("candidate-failure artifacts must be unique")
        return tuple(sorted(value, key=lambda item: (item.kind, item.path, item.sha256)))

    @model_validator(mode="after")
    def validate_candidate_failure(self) -> Self:
        if (
            self.session_receipt.status is not ProposalSessionStatus.CANDIDATE_FAILURE
            or self.session_receipt.trial_record_permitted
        ):
            raise ValueError("candidate-failure import requires a non-importable failure receipt")
        return self


@dataclass(frozen=True)
class ProposalNodeImportAuthority:
    """One proposal node receipt and its host-observed authority basis."""

    node_id: str
    receipt_sha256: str
    basis: StoredBasis


@dataclass(frozen=True)
class ProposalTrialImportAuthority:
    """Complete execution-to-import origin chain for one scored proposal trial."""

    provider_dispatch_authority: StoredBasis
    execution_receipt: StoredBasis
    node_receipts: tuple[ProposalNodeImportAuthority, ...]
    session_receipt: StoredBasis
    verifier_evidence: StoredBasis
    trial_record: StoredBasis
    import_receipt: StoredBasis
    authority_event: StoredAuthorityEvent


@dataclass(frozen=True)
class GovernedProposalTrialImport:
    """Persisted complete TrialRecord and its replayable scored-import authority."""

    record: TrialRecord
    record_path: Path
    record_artifact: ArtifactReference
    import_receipt: ProposalTrialImportReceipt
    import_receipt_path: Path
    import_receipt_artifact: ArtifactReference
    harbor_execution_receipt_path: Path
    authority: ProposalTrialImportAuthority
    consumption_claim: ProposalImportConsumptionClaim
    consumption_claim_path: Path
    terminal_record: ProposalImportTerminalRecord
    terminal_record_path: Path


@dataclass(frozen=True)
class GovernedProposalCandidateFailureImport:
    """Persisted candidate-failure evidence with no TrialRecord or import authority."""

    evidence: ProposalHarborImportEvidence
    failure_record: ProposalCandidateFailureRecord
    failure_record_path: Path
    failure_record_artifact: ArtifactReference
    harbor_execution_receipt_path: Path
    consumption_claim: ProposalImportConsumptionClaim
    consumption_claim_path: Path
    terminal_record: ProposalImportTerminalRecord
    terminal_record_path: Path


ProposalTrialImportResult = GovernedProposalTrialImport | GovernedProposalCandidateFailureImport


@dataclass(frozen=True)
class WorldLineage:
    """Content identities for the immutable task world used by one import."""

    package_sha256: str
    topology_sha256: str


@dataclass(frozen=True)
class PersistedProposalArtifacts:
    """Static proposal inputs preserved before terminal evidence is imported."""

    candidate_manifest: ArtifactReference
    graph: ArtifactReference
    freeze: ArtifactReference
    compilation: ArtifactReference
    session_plan: ArtifactReference
    bundle: ArtifactReference
    fixed_harness: ArtifactReference
    dispatch: ArtifactReference

    @property
    def all(self) -> tuple[ArtifactReference, ...]:
        return (
            self.candidate_manifest,
            self.graph,
            self.freeze,
            self.compilation,
            self.session_plan,
            self.bundle,
            self.fixed_harness,
            self.dispatch,
        )
