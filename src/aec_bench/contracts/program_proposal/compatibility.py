# ABOUTME: Preserves the historical proposal-freeze v1 wire contract for real artifact replay.
# ABOUTME: Isolates provider-calibration lifecycle fields from the phase-neutral proposal surface.

from __future__ import annotations

from typing import Literal, Self

from pydantic import (
    Field,
    SerializerFunctionWrapHandler,
    field_validator,
    model_serializer,
    model_validator,
)

from aec_bench.contracts.authority import OperatorAuthority
from aec_bench.contracts.evaluation_plane import CandidateManifestScope, EvaluationPlanRef
from aec_bench.contracts.harness_kernel import ContentAddressedModel, validate_sha256
from aec_bench.contracts.program_proposal._canonical import canonical_unique_models
from aec_bench.contracts.program_proposal.candidate import (
    CandidateGenerationManifest,
    ProgramCandidateRef,
)
from aec_bench.contracts.program_proposal.freeze import (
    _proposal_coordinate_map,
    _validate_freeze_candidate_policy_bindings,
    _validate_freeze_evaluation_manifest_binding,
    _validate_freeze_incumbent,
    _validate_freeze_operator,
    _validate_freeze_problem_view_bindings,
    _validate_realized_proposal_set,
)
from aec_bench.contracts.program_proposal.problem import (
    DecompositionLeakageAudit,
    DecompositionProblemView,
)
from aec_bench.contracts.program_proposal.types import OptimizationSplit
from aec_bench.contracts.validators import NonEmptyStr


class ProposalFreeze(ContentAddressedModel):
    """Historical v1 freeze retained for structural and provider-calibration replay."""

    schema_version: Literal["aecbench.proposal-freeze.v1"] = "aecbench.proposal-freeze.v1"
    freeze_id: NonEmptyStr
    evaluation_plan_ref: EvaluationPlanRef
    evaluation_plan_candidate_manifest_sha256: str
    evaluation_plan_candidate_scope: CandidateManifestScope | None = None
    structural_split_sha256: str
    selected_structural_item_sha256: str | None = None
    selected_provider_calibration_task_sha256: str | None = None
    provider_calibration_manifest_sha256: str | None = None
    provider_calibration_release_authority_event_sha256: str | None = None
    provider_calibration_evaluation_seed: int | None = Field(
        default=None,
        ge=0,
    )
    selected_world_lineage_id: str
    fixed_harness_sha256: str
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
        "evaluation_plan_candidate_manifest_sha256",
        "structural_split_sha256",
        "selected_world_lineage_id",
        "fixed_harness_sha256",
        "proposal_policy_sha256",
        "policy_checkpoint_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator(
        "selected_structural_item_sha256",
        "selected_provider_calibration_task_sha256",
        "provider_calibration_manifest_sha256",
        "provider_calibration_release_authority_event_sha256",
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
            raise TypeError("proposal freeze serialization must produce an object")
        if self.split is not OptimizationSplit.PROVIDER_CALIBRATION:
            payload.pop("selected_provider_calibration_task_sha256", None)
            payload.pop("provider_calibration_manifest_sha256", None)
            payload.pop(
                "provider_calibration_release_authority_event_sha256",
                None,
            )
            payload.pop("provider_calibration_evaluation_seed", None)
        if self.evaluation_plan_candidate_scope is None:
            payload.pop("evaluation_plan_candidate_scope", None)
        if self.execution_profile_sha256 is None:
            payload.pop("execution_profile_sha256", None)
        if self.incumbent_candidate is None:
            payload.pop("incumbent_candidate", None)
        return payload

    @model_validator(mode="after")
    def validate_freeze_bindings(self) -> Self:
        _validate_freeze_operator(self)
        _validate_freeze_problem_view_bindings(self)
        _validate_freeze_evaluation_manifest_binding(self)
        _validate_freeze_candidate_policy_bindings(self)
        _validate_freeze_split_lifecycle(self)
        expected_candidates = _proposal_coordinate_map(self.candidate_manifest)
        _validate_realized_proposal_set(self, expected_candidates)
        _validate_freeze_incumbent(self, expected_candidates)
        return self


def _validate_freeze_split_lifecycle(freeze: ProposalFreeze) -> None:
    if freeze.split is OptimizationSplit.PROVIDER_CALIBRATION:
        _validate_provider_calibration_freeze_fields(freeze)
        return
    _validate_structural_freeze_fields(freeze)


def _validate_provider_calibration_freeze_fields(freeze: ProposalFreeze) -> None:
    fields_incomplete = (
        freeze.selected_structural_item_sha256 is not None
        or freeze.selected_provider_calibration_task_sha256 is None
        or freeze.provider_calibration_manifest_sha256 is None
        or freeze.provider_calibration_release_authority_event_sha256 is None
        or freeze.provider_calibration_evaluation_seed is None
    )
    if fields_incomplete:
        raise ValueError("provider calibration freeze requires exact manifest, task, and release authority")


def _validate_structural_freeze_fields(freeze: ProposalFreeze) -> None:
    carries_provider_calibration_evidence = (
        freeze.selected_structural_item_sha256 is None
        or freeze.selected_provider_calibration_task_sha256 is not None
        or freeze.provider_calibration_manifest_sha256 is not None
        or freeze.provider_calibration_release_authority_event_sha256 is not None
        or freeze.provider_calibration_evaluation_seed is not None
    )
    if carries_provider_calibration_evidence:
        raise ValueError("structural proposal freeze cannot carry provider calibration lifecycle evidence")
