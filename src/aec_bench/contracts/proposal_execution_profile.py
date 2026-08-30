# ABOUTME: Defines the phase-neutral policy surface for proposal compilation and execution.
# ABOUTME: Pins kernel operations, harness topology, lowering limits, and scheduling environments.

from __future__ import annotations

from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from aec_bench.contracts.content_address import ContentAddressedModel
from aec_bench.contracts.harness_instance import ProgramOperationScope
from aec_bench.contracts.harness_kernel import (
    FrozenStrictModel,
    KernelCapabilityRef,
    validate_sha256,
)
from aec_bench.contracts.validators import NonEmptyStr


class ProposalSchedulingSemantics(StrEnum):
    """Execution order that a proposal runtime is permitted to realize."""

    SEQUENTIAL_DATAFLOW = "sequential_dataflow"
    READY_SET_DATAFLOW = "ready_set_dataflow"


class ProposalEnvironmentPolicy(StrEnum):
    """Environment ownership required by one scheduling policy."""

    ROTATED_SINGLE_ENVIRONMENT = "rotated_single_environment"
    ISOLATED_ENVIRONMENT_POOL = "isolated_environment_pool"


class ProposalOperationConstraint(FrozenStrictModel):
    """Exact fixed-kernel operation admitted by one proposal profile."""

    operation_id: NonEmptyStr
    operation_definition_sha256: str
    capability_ref: KernelCapabilityRef
    required_scope: ProgramOperationScope
    max_parallelism: int = Field(ge=1, le=256)
    supports_retry: bool
    retry_safe_error_codes: tuple[NonEmptyStr, ...] = ()
    supports_recursion: bool

    @field_validator("operation_definition_sha256")
    @classmethod
    def validate_definition_hash(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("retry_safe_error_codes")
    @classmethod
    def canonicalize_retry_codes(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("proposal operation retry-safe error codes must be unique")
        return tuple(sorted(value))

    @model_validator(mode="after")
    def validate_retry_surface(self) -> Self:
        if not self.supports_retry and self.retry_safe_error_codes:
            raise ValueError("proposal operation without retry support cannot declare retry-safe errors")
        return self


class ProposalHarnessTopologyPolicy(FrozenStrictModel):
    """Binding-cardinality limits supported by proposal budget allocation."""

    required_agent_binding_count: int = Field(ge=1, le=32)
    max_context_binding_count: int = Field(ge=0, le=32)
    max_tool_binding_count: int = Field(ge=0, le=32)


class ProposalExecutionSurfacePolicy(FrozenStrictModel):
    """Provider, adapter, completion, and tool surface admitted at runtime."""

    adapter_kind: Literal["direct", "tool_loop", "rlm", "lambda-rlm"]
    completion_policy: Literal[
        "explicit_final",
        "task_output_contract",
        "task_output_commit",
    ]
    allowed_tool_ids: tuple[NonEmptyStr, ...]
    allowed_backends: tuple[
        Literal["docker", "modal", "e2b", "daytona", "morph"],
        ...,
    ] = Field(min_length=1)
    provider_broker_required: bool

    @field_validator("allowed_tool_ids", "allowed_backends")
    @classmethod
    def canonicalize_surface_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("proposal execution surface identities must be unique")
        return tuple(sorted(value))

    @model_validator(mode="after")
    def validate_completion_surface(self) -> Self:
        if self.completion_policy != "explicit_final" and self.adapter_kind != "rlm":
            raise ValueError("proposal output-contract completion requires the RLM adapter")
        return self


class ProposalLoweringPolicy(FrozenStrictModel):
    """Graph and control-flow limits enforced during proposal lowering."""

    max_semantic_subtasks: int = Field(ge=1, le=10_000)
    max_fan_in: int = Field(ge=1, le=10_000)
    max_fan_out: int = Field(ge=1, le=10_000)
    allow_retry: bool
    allow_recursion: bool


class ProposalSchedulingPolicy(FrozenStrictModel):
    """Deterministic scheduling and environment-isolation policy."""

    semantics: ProposalSchedulingSemantics
    max_parallelism: int = Field(ge=1, le=256)
    environment_policy: ProposalEnvironmentPolicy
    deterministic_commit_order: Literal[True]

    @model_validator(mode="after")
    def validate_environment_realizes_scheduling(self) -> Self:
        if self.semantics is ProposalSchedulingSemantics.SEQUENTIAL_DATAFLOW:
            if (
                self.max_parallelism != 1
                or self.environment_policy is not ProposalEnvironmentPolicy.ROTATED_SINGLE_ENVIRONMENT
            ):
                raise ValueError(
                    "sequential proposal scheduling requires one rotated environment",
                )
        elif self.environment_policy is not ProposalEnvironmentPolicy.ISOLATED_ENVIRONMENT_POOL:
            raise ValueError(
                "ready-set proposal scheduling requires an isolated environment pool",
            )
        return self


class ProposalExecutionProfile(ContentAddressedModel):
    """Content-addressed policy shared by freeze, compiler, dispatch, and import."""

    schema_version: Literal["aecbench.proposal-execution-profile.v1"] = "aecbench.proposal-execution-profile.v1"
    profile_id: NonEmptyStr
    version: NonEmptyStr
    required_kernel_id: NonEmptyStr
    required_kernel_version: NonEmptyStr
    operation_constraints: tuple[ProposalOperationConstraint, ...] = Field(
        min_length=1,
    )
    harness_topology: ProposalHarnessTopologyPolicy
    execution_surface: ProposalExecutionSurfacePolicy
    lowering: ProposalLoweringPolicy
    scheduling: ProposalSchedulingPolicy

    @field_validator("operation_constraints")
    @classmethod
    def canonicalize_operation_constraints(
        cls,
        value: tuple[ProposalOperationConstraint, ...],
    ) -> tuple[ProposalOperationConstraint, ...]:
        operation_ids = tuple(item.operation_id for item in value)
        if len(operation_ids) != len(set(operation_ids)):
            raise ValueError("proposal execution profile operation ids must be unique")
        capability_refs = tuple(
            (
                item.capability_ref.capability_id,
                item.capability_ref.version,
            )
            for item in value
        )
        if len(capability_refs) != len(set(capability_refs)):
            raise ValueError("proposal execution profile capability refs must be unique")
        definition_sha256s = tuple(item.operation_definition_sha256 for item in value)
        if len(definition_sha256s) != len(set(definition_sha256s)):
            raise ValueError(
                "proposal execution profile operation definitions must be unique",
            )
        return tuple(sorted(value, key=lambda item: item.operation_id))

    @property
    def required_operation_ids(self) -> tuple[str, ...]:
        """Return the exact canonical fixed-kernel operation IDs."""

        return tuple(item.operation_id for item in self.operation_constraints)

    def operation(self, operation_id: str) -> ProposalOperationConstraint | None:
        """Resolve one operation constraint by its stable ID."""

        return next(
            (item for item in self.operation_constraints if item.operation_id == operation_id),
            None,
        )
