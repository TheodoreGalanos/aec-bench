# ABOUTME: Defines the exact evidence, basis, and result contracts for proposal freezing.
# ABOUTME: Validates complete candidate, profile, authority, and replay bindings.

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Self

from pydantic import (
    Field,
    SerializerFunctionWrapHandler,
    field_validator,
    model_serializer,
    model_validator,
)

from aec_bench.contracts.authority import (
    AuthorityAction,
    AuthorityDecision,
    AuthorityEvent,
    AuthorityPrincipal,
    AuthorityPrincipalKind,
    BasisKind,
    BasisReference,
)
from aec_bench.contracts.legacy_content_address import LegacyContentAddressedModel
from aec_bench.contracts.program_proposal.candidate import ProgramCandidateRef
from aec_bench.contracts.program_proposal.freeze import ProposalFreeze
from aec_bench.experimentation.governance.standing_monitors import (
    BasisReplayObservation,
    BasisReplayRequirement,
)


class GovernedProposalFreezeError(ValueError):
    """Raised when exact proposal-freeze evidence cannot safely grant authority."""


@dataclass(frozen=True)
class ProposalArtifact:
    """Exact proposal bytes and their non-authoritative producing principal."""

    reference: ProgramCandidateRef
    content: bytes
    producer: AuthorityPrincipal
    producer_process_id: str
    invocation_id: str


@dataclass(frozen=True)
class IncumbentArtifact:
    """Exact host-policy bytes for the preregistered monolithic control."""

    reference: ProgramCandidateRef
    content: bytes
    producer: AuthorityPrincipal
    producer_process_id: str
    invocation_id: str


@dataclass(frozen=True)
class ObservedInputBasis:
    """Internal join of exact input references and their complete origin closure."""

    evaluation_plan: BasisReference
    evaluation_plan_candidate_scope: BasisReference | None
    operator_authority: BasisReference
    structural_split: BasisReference
    leakage_audit: BasisReference
    problem_view: BasisReference
    candidate_manifest: BasisReference
    fixed_harness: BasisReference
    execution_profile: BasisReference | None
    proposal_policy: BasisReference
    policy_checkpoint: BasisReference
    proposal_artifacts: tuple[BasisReference, ...]
    incumbent_artifact: BasisReference | None
    parent_origin_sha256s: tuple[str, ...]


@dataclass(frozen=True)
class SelectedTaskBinding:
    """Exact selected structural item identity."""

    content_sha256: str
    review_lineage_id: str


class ProposalFreezeBasis(LegacyContentAddressedModel):
    """Complete reference set for the host-confined proposal-freeze evidence."""

    schema_version: Literal["aecbench.proposal-freeze-basis.v1"] = "aecbench.proposal-freeze-basis.v1"
    evaluation_plan: BasisReference
    evaluation_plan_candidate_scope: BasisReference | None = None
    operator_authority: BasisReference
    structural_split: BasisReference
    leakage_audit: BasisReference
    problem_view: BasisReference
    candidate_manifest: BasisReference
    fixed_harness: BasisReference
    execution_profile: BasisReference | None = None
    proposal_policy: BasisReference
    policy_checkpoint: BasisReference
    proposal_artifacts: tuple[BasisReference, ...] = Field(min_length=1)
    incumbent_artifact: BasisReference | None = None
    freeze: BasisReference

    @field_validator("proposal_artifacts")
    @classmethod
    def canonicalize_proposal_artifacts(
        cls,
        value: tuple[BasisReference, ...],
    ) -> tuple[BasisReference, ...]:
        identities = tuple(reference.artifact_id for reference in value)
        if len(identities) != len(set(identities)):
            raise ValueError(
                "proposal artifact basis identities must be unique",
            )
        return tuple(
            sorted(value, key=lambda reference: reference.artifact_id),
        )

    @model_serializer(mode="wrap")
    def serialize_basis(
        self,
        handler: SerializerFunctionWrapHandler,
    ) -> dict[str, object]:
        payload = handler(self)
        if not isinstance(payload, dict):
            raise TypeError(
                "proposal freeze basis serialization must produce an object",
            )
        if self.incumbent_artifact is None:
            payload.pop("incumbent_artifact", None)
        if self.evaluation_plan_candidate_scope is None:
            payload.pop("evaluation_plan_candidate_scope", None)
        if self.execution_profile is None:
            payload.pop("execution_profile", None)
        return payload

    @model_validator(mode="after")
    def validate_basis_kinds_and_uniqueness(self) -> Self:
        references = self.references
        if any(reference.kind is not BasisKind.EVIDENCE for reference in references):
            raise ValueError(
                "proposal-freeze basis artifacts must use the evidence basis kind",
            )
        identities = tuple(
            (
                reference.kind,
                reference.artifact_id,
                reference.artifact_sha256,
            )
            for reference in references
        )
        if len(identities) != len(set(identities)):
            raise ValueError(
                "proposal-freeze basis references must be unique",
            )
        return self

    @property
    def references(self) -> tuple[BasisReference, ...]:
        """Return the exact basis tuple in AuthorityEvent canonical order."""

        optional = tuple(
            reference
            for reference in (
                self.evaluation_plan_candidate_scope,
                self.execution_profile,
            )
            if reference is not None
        )
        return tuple(
            sorted(
                (
                    self.evaluation_plan,
                    self.operator_authority,
                    self.structural_split,
                    *optional,
                    self.leakage_audit,
                    self.problem_view,
                    self.candidate_manifest,
                    self.fixed_harness,
                    self.proposal_policy,
                    self.policy_checkpoint,
                    *self.proposal_artifacts,
                    *(() if self.incumbent_artifact is None else (self.incumbent_artifact,)),
                    self.freeze,
                ),
                key=lambda reference: (
                    reference.kind.value,
                    reference.artifact_id,
                    reference.artifact_sha256,
                ),
            ),
        )


class GovernedProposalFreezeResult(LegacyContentAddressedModel):
    """Host-side freeze authority without full evaluation-plan or proposal payloads."""

    schema_version: Literal["aecbench.governed-proposal-freeze-result.v1"] = (
        "aecbench.governed-proposal-freeze-result.v1"
    )
    freeze: ProposalFreeze
    basis: ProposalFreezeBasis
    authority_event: AuthorityEvent
    replay_requirement: BasisReplayRequirement
    replay_observation: BasisReplayObservation

    @model_validator(mode="after")
    def validate_result_bindings(self) -> Self:
        scope = f"proposal-freeze.{self.freeze.freeze_id}"
        _validate_result_authority(
            freeze=self.freeze,
            basis=self.basis,
            event=self.authority_event,
        )
        _validate_result_candidate_basis(
            freeze=self.freeze,
            basis=self.basis,
            scope=scope,
        )
        _validate_result_profile_basis(
            freeze=self.freeze,
            basis=self.basis,
            scope=scope,
        )
        _validate_result_replay(
            event=self.authority_event,
            requirement=self.replay_requirement,
            observation=self.replay_observation,
        )
        return self


def _validate_result_authority(
    *,
    freeze: ProposalFreeze,
    basis: ProposalFreezeBasis,
    event: AuthorityEvent,
) -> None:
    if (
        event.action is not AuthorityAction.PROPOSAL_FREEZE
        or event.decision is not AuthorityDecision.GRANTED
        or event.principal.kind is not AuthorityPrincipalKind.HOST_POLICY
    ):
        raise ValueError(
            "proposal freeze result requires granted host-policy freeze authority",
        )
    if event.subject_id != freeze.freeze_id or event.subject_sha256 != freeze.content_sha256:
        raise ValueError(
            "proposal freeze authority does not bind the exact proposal freeze",
        )
    if event.kernel_ref != freeze.problem_view.fixed_harness.kernel_ref:
        raise ValueError(
            "proposal freeze authority kernel does not match the frozen problem view",
        )
    if event.basis != basis.references:
        raise ValueError(
            "proposal freeze authority does not carry the complete frozen basis",
        )


def _validate_result_candidate_basis(
    *,
    freeze: ProposalFreeze,
    basis: ProposalFreezeBasis,
    scope: str,
) -> None:
    if basis.freeze.artifact_id != f"{scope}.freeze":
        raise ValueError(
            "proposal freeze basis does not identify the exact freeze",
        )
    expected_proposal_ids = {
        f"{scope}.proposal-artifact.{candidate.candidate_id}" for candidate in freeze.realized_candidates
    }
    actual_proposal_ids = {reference.artifact_id for reference in basis.proposal_artifacts}
    if actual_proposal_ids != expected_proposal_ids:
        raise ValueError(
            "proposal artifact basis does not cover the exact frozen candidates",
        )
    expected_incumbent_id = (
        None
        if freeze.incumbent_candidate is None
        else (f"{scope}.incumbent-artifact.{freeze.incumbent_candidate.candidate_id}")
    )
    actual_incumbent_id = None if basis.incumbent_artifact is None else basis.incumbent_artifact.artifact_id
    if actual_incumbent_id != expected_incumbent_id:
        raise ValueError(
            "incumbent artifact basis does not match the frozen incumbent",
        )


def _validate_result_profile_basis(
    *,
    freeze: ProposalFreeze,
    basis: ProposalFreezeBasis,
    scope: str,
) -> None:
    if freeze.execution_profile_sha256 is None:
        if basis.execution_profile is not None:
            raise ValueError(
                "profile-less proposal freeze cannot carry an execution-profile basis",
            )
        return
    if (
        basis.execution_profile is None
        or basis.execution_profile.artifact_id != f"{scope}.execution-profile.{freeze.execution_profile_sha256}"
    ):
        raise ValueError(
            "proposal freeze result does not bind its exact execution-profile basis",
        )


def _validate_result_replay(
    *,
    event: AuthorityEvent,
    requirement: BasisReplayRequirement,
    observation: BasisReplayObservation,
) -> None:
    if requirement.authority_event_id != event.event_id or requirement.authority_event_sha256 != event.content_sha256:
        raise ValueError(
            "basis replay requirement does not bind the proposal freeze event",
        )
    if (
        observation.requirement_sha256 != requirement.content_sha256
        or not observation.replayed
        or not observation.closure_complete
        or observation.observed_basis_closure_sha256 != requirement.basis_closure_sha256
    ):
        raise ValueError(
            "proposal freeze requires an immediate complete basis replay",
        )
