# ABOUTME: Defines frozen candidate-generation manifests and immutable program candidate references.
# ABOUTME: Keeps candidate origin and preregistered generation coordinates separate from evaluation.

from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from aec_bench.contracts.harness_kernel import (
    ContentAddressedModel,
    FrozenStrictModel,
    validate_sha256,
)
from aec_bench.contracts.program_proposal.types import ProgramCandidateKind
from aec_bench.contracts.validators import NonEmptyStr


class CandidateGenerationCoordinate(FrozenStrictModel):
    """One preregistered policy draw in a fixed candidate-generation manifest."""

    coordinate_id: NonEmptyStr
    candidate_id: NonEmptyStr
    seed: int = Field(ge=0)


class CandidateGenerationManifest(ContentAddressedModel):
    """Frozen policy draws and stopping identity for one complete proposal set."""

    schema_version: Literal["aecbench.candidate-generation-manifest.v1"] = "aecbench.candidate-generation-manifest.v1"
    manifest_id: NonEmptyStr
    problem_view_sha256: str
    proposal_policy_sha256: str
    policy_checkpoint_sha256: str
    selection_policy_sha256: str
    expected_candidate_count: int = Field(ge=1)
    coordinates: tuple[CandidateGenerationCoordinate, ...] = Field(min_length=1)
    stopping_policy_sha256: str

    @field_validator(
        "problem_view_sha256",
        "proposal_policy_sha256",
        "policy_checkpoint_sha256",
        "selection_policy_sha256",
        "stopping_policy_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("coordinates")
    @classmethod
    def canonicalize_coordinates(
        cls,
        value: tuple[CandidateGenerationCoordinate, ...],
    ) -> tuple[CandidateGenerationCoordinate, ...]:
        coordinate_ids = [coordinate.coordinate_id for coordinate in value]
        candidate_ids = [coordinate.candidate_id for coordinate in value]
        seeds = [coordinate.seed for coordinate in value]
        if len(coordinate_ids) != len(set(coordinate_ids)):
            raise ValueError("candidate generation coordinate ids must be unique")
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("candidate generation candidate ids must be unique")
        if len(seeds) != len(set(seeds)):
            raise ValueError("candidate generation seeds must be unique")
        return tuple(sorted(value, key=lambda coordinate: coordinate.coordinate_id))

    @model_validator(mode="after")
    def validate_candidate_count(self) -> Self:
        if len(self.coordinates) != self.expected_candidate_count:
            raise ValueError("candidate count must match the preregistered coordinates")
        return self


class ProgramCandidateRef(ContentAddressedModel):
    """Immutable identity of an incumbent or frozen proposal program."""

    schema_version: Literal["aecbench.program-candidate-ref.v1"] = "aecbench.program-candidate-ref.v1"
    candidate_id: NonEmptyStr
    kind: ProgramCandidateKind
    candidate_artifact_sha256: str
    generation_coordinate_id: NonEmptyStr | None = None

    @field_validator("candidate_artifact_sha256")
    @classmethod
    def validate_candidate_artifact_hash(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_origin(self) -> Self:
        if self.kind is ProgramCandidateKind.PROPOSAL and self.generation_coordinate_id is None:
            raise ValueError("proposal candidate requires a generation coordinate")
        if self.kind is ProgramCandidateKind.INCUMBENT and self.generation_coordinate_id is not None:
            raise ValueError("incumbent candidate cannot claim a generation coordinate")
        return self
