# ABOUTME: Defines proposal policy, effect budget, cardinality, and execution-profile design data.
# ABOUTME: Validates generation completeness without embedding experiment-specific constants.

from __future__ import annotations

import hashlib
from typing import Literal, Self

from pydantic import Field, FiniteFloat, field_validator, model_validator

from aec_bench.contracts.harness_kernel import (
    ContentAddressedModel,
    FrozenStrictModel,
    validate_sha256,
)
from aec_bench.contracts.program_proposal.types import ProgramCandidateKind
from aec_bench.contracts.validators import NonEmptyStr


class ProposalGenerationPolicy(ContentAddressedModel):
    """Executable proposer bytes and limits without experiment-specific literals."""

    schema_version: Literal["aecbench.proposal-generation-policy.v2"] = "aecbench.proposal-generation-policy.v2"
    policy_id: NonEmptyStr
    version: NonEmptyStr
    instruction_bytes: bytes = Field(min_length=1)
    instruction_sha256: str
    model_id: NonEmptyStr
    policy_checkpoint_sha256: str
    grammar_sha256: str
    max_turns: int = Field(ge=1)
    max_observed_tokens: int = Field(ge=1)
    max_cost_usd: FiniteFloat = Field(gt=0)
    max_wall_time_seconds: int = Field(ge=1)
    expected_candidate_count: int = Field(ge=1)

    @field_validator(
        "instruction_sha256",
        "policy_checkpoint_sha256",
        "grammar_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_instruction_identity(self) -> Self:
        expected = hashlib.sha256(self.instruction_bytes).hexdigest()
        if self.instruction_sha256 != expected:
            raise ValueError(
                "proposal-generation instruction identity must match the exact bytes",
            )
        return self


class EvaluationExecutionProfileRef(FrozenStrictModel):
    """Content-pinned proposal compilation and execution profile."""

    profile_id: NonEmptyStr
    version: NonEmptyStr
    content_sha256: str

    @field_validator("content_sha256")
    @classmethod
    def validate_profile_hash(cls, value: str) -> str:
        return validate_sha256(value)


class CandidateKindRequirement(FrozenStrictModel):
    """Required number of one candidate kind in every task schedule."""

    kind: ProgramCandidateKind
    count_per_task: int = Field(ge=1)


class EvaluationGenerationBudget(ContentAddressedModel):
    """Whole-generation limits supplied by an experiment specification."""

    schema_version: Literal["aecbench.evaluation-generation-budget.v2"] = "aecbench.evaluation-generation-budget.v2"
    task_count: int = Field(ge=1)
    proposer_invocation_count: int = Field(ge=1)
    assignment_count: int = Field(ge=1)
    primary_execution_attempt_count: int = Field(ge=1)
    max_no_effect_retry_count: int = Field(ge=0)
    max_execution_attempt_count: int = Field(ge=1)
    planned_high_level_invocation_count: int = Field(ge=1)
    max_total_attempt_count: int = Field(ge=1)
    max_main_model_turns: int = Field(ge=1)
    max_auxiliary_compaction_calls: int = Field(ge=0)
    max_raw_provider_calls: int = Field(ge=1)
    max_observed_tokens: int = Field(ge=1)
    max_cost_usd: FiniteFloat = Field(gt=0)
    max_wall_time_seconds: int = Field(ge=1)
    max_concurrency: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_derived_limits(self) -> Self:
        if self.primary_execution_attempt_count + self.max_no_effect_retry_count != self.max_execution_attempt_count:
            raise ValueError(
                "maximum execution attempts must equal primary attempts plus no-effect retries",
            )
        if self.max_main_model_turns + self.max_auxiliary_compaction_calls != self.max_raw_provider_calls:
            raise ValueError(
                "raw provider-call limit must equal main turns plus auxiliary calls",
            )
        if self.max_total_attempt_count < self.planned_high_level_invocation_count:
            raise ValueError(
                "total attempt ceiling cannot be below planned high-level invocations",
            )
        if self.max_concurrency > self.max_execution_attempt_count:
            raise ValueError(
                "generation concurrency cannot exceed the execution-attempt ceiling",
            )
        return self


class EvaluationGenerationSpec(ContentAddressedModel):
    """Phase-neutral design against which a generation is checked for completeness."""

    schema_version: Literal["aecbench.evaluation-generation-spec.v2"] = "aecbench.evaluation-generation-spec.v2"
    spec_id: NonEmptyStr
    task_count: int = Field(ge=1)
    proposer_invocations_per_task: int = Field(ge=1)
    candidate_kind_requirements: tuple[CandidateKindRequirement, ...] = Field(
        min_length=1,
    )
    assignment_count_per_task: int = Field(ge=1)
    total_assignment_count: int = Field(ge=1)
    effect_budget: EvaluationGenerationBudget
    execution_profile: EvaluationExecutionProfileRef

    @field_validator("candidate_kind_requirements")
    @classmethod
    def canonicalize_candidate_requirements(
        cls,
        value: tuple[CandidateKindRequirement, ...],
    ) -> tuple[CandidateKindRequirement, ...]:
        kinds = tuple(item.kind for item in value)
        if len(kinds) != len(set(kinds)):
            raise ValueError("evaluation candidate-kind requirements must be unique")
        return tuple(sorted(value, key=lambda item: item.kind.value))

    @model_validator(mode="after")
    def validate_design_arithmetic(self) -> Self:
        requirement_count = sum(requirement.count_per_task for requirement in self.candidate_kind_requirements)
        if requirement_count != self.assignment_count_per_task:
            raise ValueError(
                "assignment count per task must equal the candidate-kind requirements",
            )
        if self.total_assignment_count != (self.task_count * self.assignment_count_per_task):
            raise ValueError(
                "total assignment count must equal task and per-task cardinalities",
            )
        proposal_count = self.candidate_count(ProgramCandidateKind.PROPOSAL)
        if proposal_count < 1:
            raise ValueError(
                "evaluation generation requires at least one proposal per task",
            )
        budget = self.effect_budget
        if budget.task_count != self.task_count:
            raise ValueError("generation budget task count differs from its spec")
        expected_proposer_invocations = self.task_count * self.proposer_invocations_per_task
        if budget.proposer_invocation_count != expected_proposer_invocations:
            raise ValueError(
                "generation budget proposer invocation count differs from its spec",
            )
        if (
            budget.assignment_count != self.total_assignment_count
            or budget.primary_execution_attempt_count != self.total_assignment_count
        ):
            raise ValueError(
                "generation budget assignment and primary execution counts differ from its spec",
            )
        return self

    def candidate_count(self, kind: ProgramCandidateKind) -> int:
        """Return the per-task count declared for one candidate kind."""

        return next(
            (
                requirement.count_per_task
                for requirement in self.candidate_kind_requirements
                if requirement.kind is kind
            ),
            0,
        )

    @property
    def proposal_candidate_count_per_task(self) -> int:
        """Return the proposal count expected from each prepared task."""

        return self.candidate_count(ProgramCandidateKind.PROPOSAL)


class EvaluationGenerationSourceRef(FrozenStrictModel):
    """Historical contract identity retained by an execution-only compatibility view."""

    role: Literal["cohort", "preparation", "batch"]
    schema_version: NonEmptyStr
    content_sha256: str

    @field_validator("content_sha256")
    @classmethod
    def validate_source_hash(cls, value: str) -> str:
        return validate_sha256(value)
