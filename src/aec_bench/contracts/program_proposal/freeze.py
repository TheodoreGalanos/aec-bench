# ABOUTME: Defines the phase-neutral proposal freeze and its shared binding validation.
# ABOUTME: Keeps generic evaluation-cohort lifecycle rules separate from historical replay.

from __future__ import annotations

from typing import Literal, Protocol, Self

from pydantic import (
    Field,
    SerializerFunctionWrapHandler,
    field_validator,
    model_serializer,
    model_validator,
)

from aec_bench.contracts.authority import OperatorAuthority, OperatorRole
from aec_bench.contracts.evaluation_generation.cohort import EvaluationCohortBinding
from aec_bench.contracts.evaluation_plane import CandidateManifestScope
from aec_bench.contracts.evaluation_refs import EvaluationRegimeRef
from aec_bench.contracts.harness_instance import HarnessInstanceRef
from aec_bench.contracts.harness_kernel import validate_sha256
from aec_bench.contracts.legacy_content_address import LegacyContentAddressedModel
from aec_bench.contracts.program_proposal._canonical import canonical_unique_models
from aec_bench.contracts.program_proposal.candidate import (
    CandidateGenerationManifest,
    ProgramCandidateRef,
)
from aec_bench.contracts.program_proposal.problem import (
    DecompositionLeakageAudit,
    DecompositionProblemView,
)
from aec_bench.contracts.program_proposal.types import (
    OptimizationSplit,
    ProgramCandidateKind,
)
from aec_bench.contracts.validators import NonEmptyStr


class ProposalFreezeBindings(Protocol):
    """Structural fields used by the current proposal-freeze validators."""

    evaluation_assignment_candidate_scope: CandidateManifestScope | None
    operator_authority: OperatorAuthority
    leakage_audit: DecompositionLeakageAudit
    problem_view: DecompositionProblemView
    candidate_manifest: CandidateGenerationManifest
    proposal_policy_sha256: str
    policy_checkpoint_sha256: str
    realized_candidates: tuple[ProgramCandidateRef, ...]
    incumbent_candidate: ProgramCandidateRef | None


class ProposalFreeze(LegacyContentAddressedModel):
    """Phase-neutral host freeze binding proposals to an optional evaluation cohort."""

    schema_version: Literal["aecbench.evaluation-proposal-freeze.v3"] = "aecbench.evaluation-proposal-freeze.v3"
    freeze_id: NonEmptyStr
    evaluation_regime_ref: EvaluationRegimeRef
    evaluation_assignment_candidate_scope: CandidateManifestScope | None = None
    structural_split_sha256: str
    selected_structural_item_sha256: str | None = None
    evaluation_cohort: EvaluationCohortBinding | None = None
    selected_review_lineage_id: str
    fixed_harness_ref: HarnessInstanceRef
    execution_profile_sha256: str | None = None
    operator_authority: OperatorAuthority
    split: OptimizationSplit
    leakage_audit: DecompositionLeakageAudit
    problem_view: DecompositionProblemView
    candidate_manifest: CandidateGenerationManifest
    proposal_policy_sha256: str
    policy_checkpoint_sha256: str
    realized_candidates: tuple[ProgramCandidateRef, ...] = Field(min_length=1)
    incumbent_candidate: ProgramCandidateRef | None = None
    proposal_set_closed: Literal[True]
    late_candidates_permitted: Literal[False]

    @field_validator(
        "structural_split_sha256",
        "selected_review_lineage_id",
        "proposal_policy_sha256",
        "policy_checkpoint_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator(
        "selected_structural_item_sha256",
        "execution_profile_sha256",
    )
    @classmethod
    def validate_optional_hashes(cls, value: str | None) -> str | None:
        return None if value is None else validate_sha256(value)

    @field_validator("realized_candidates")
    @classmethod
    def canonicalize_candidates(
        cls,
        value: tuple[ProgramCandidateRef, ...],
    ) -> tuple[ProgramCandidateRef, ...]:
        return canonical_unique_models(
            value,
            identity="candidate_id",
            label="realized candidates",
        )

    @model_serializer(mode="wrap")
    def serialize_freeze(
        self,
        handler: SerializerFunctionWrapHandler,
    ) -> dict[str, object]:
        payload = handler(self)
        if not isinstance(payload, dict):
            raise TypeError("evaluation proposal freeze serialization must produce an object")
        for field_name in (
            "evaluation_assignment_candidate_scope",
            "selected_structural_item_sha256",
            "evaluation_cohort",
            "execution_profile_sha256",
            "incumbent_candidate",
        ):
            if getattr(self, field_name) is None:
                payload.pop(field_name, None)
        return payload

    @model_validator(mode="after")
    def validate_freeze_bindings(self) -> Self:
        _validate_freeze_operator(self)
        _validate_freeze_problem_view_bindings(self)
        _validate_freeze_evaluation_manifest_binding(self)
        _validate_freeze_candidate_policy_bindings(self)
        _validate_evaluation_freeze_split_lifecycle(self)
        expected_candidates = _proposal_coordinate_map(self.candidate_manifest)
        _validate_realized_proposal_set(self, expected_candidates)
        _validate_freeze_incumbent(self, expected_candidates)
        return self


def _validate_freeze_operator(
    freeze: ProposalFreezeBindings,
) -> None:
    if freeze.operator_authority.role is not OperatorRole.PERFORMANCE_OPTIMIZATION:
        raise ValueError("proposal freeze requires a performance_optimization operator")


def _validate_freeze_problem_view_bindings(
    freeze: ProposalFreezeBindings,
) -> None:
    if not freeze.leakage_audit.passed:
        raise ValueError("proposal freeze requires a passed leakage audit")
    if freeze.leakage_audit.problem_view_sha256 != freeze.problem_view.content_sha256:
        raise ValueError("leakage audit does not bind the frozen problem view")
    if freeze.candidate_manifest.problem_view_sha256 != freeze.problem_view.content_sha256:
        raise ValueError("candidate manifest does not bind the frozen problem view")


def _validate_freeze_evaluation_manifest_binding(
    freeze: ProposalFreezeBindings,
) -> None:
    scope = freeze.evaluation_assignment_candidate_scope
    if scope is None:
        return
    if freeze.candidate_manifest.content_sha256 not in scope.candidate_manifest_sha256s:
        raise ValueError("candidate manifest is not a member of the evaluation assignment candidate scope")


def _validate_freeze_candidate_policy_bindings(
    freeze: ProposalFreezeBindings,
) -> None:
    if freeze.proposal_policy_sha256 != freeze.candidate_manifest.proposal_policy_sha256:
        raise ValueError("proposal policy does not match the candidate manifest")
    if freeze.policy_checkpoint_sha256 != freeze.candidate_manifest.policy_checkpoint_sha256:
        raise ValueError("policy checkpoint does not match the candidate manifest")


def _validate_evaluation_freeze_split_lifecycle(
    freeze: ProposalFreeze,
) -> None:
    if freeze.split is OptimizationSplit.CALIBRATION:
        if freeze.evaluation_cohort is None or freeze.selected_structural_item_sha256 is not None:
            raise ValueError(
                "calibration proposal freeze requires one evaluation cohort and no structural item",
            )
        return
    if freeze.evaluation_cohort is not None or freeze.selected_structural_item_sha256 is None:
        raise ValueError(
            "non-calibration proposal freeze requires one structural item and no evaluation cohort",
        )


def _proposal_coordinate_map(
    manifest: CandidateGenerationManifest,
) -> dict[str, str]:
    return {coordinate.candidate_id: coordinate.coordinate_id for coordinate in manifest.coordinates}


def _validate_realized_proposal_set(
    freeze: ProposalFreezeBindings,
    expected_candidates: dict[str, str],
) -> None:
    realized_candidates = {
        candidate.candidate_id: candidate.generation_coordinate_id
        for candidate in freeze.realized_candidates
        if candidate.kind is ProgramCandidateKind.PROPOSAL
    }
    if len(realized_candidates) != len(freeze.realized_candidates) or realized_candidates != expected_candidates:
        raise ValueError("proposal freeze must bind the exact realized candidate set")


def _validate_freeze_incumbent(
    freeze: ProposalFreezeBindings,
    expected_candidates: dict[str, str],
) -> None:
    incumbent = freeze.incumbent_candidate
    if incumbent is None:
        return
    if incumbent.kind is not ProgramCandidateKind.INCUMBENT:
        raise ValueError("proposal freeze incumbent must have incumbent candidate kind")
    if incumbent.candidate_id in expected_candidates:
        raise ValueError("proposal freeze incumbent must be distinct from every proposal")
