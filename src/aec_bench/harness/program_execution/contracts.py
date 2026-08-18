# ABOUTME: Defines immutable execution outcomes and lineage evidence for compiled program runs.
# ABOUTME: Keeps operation, node, and terminal program evidence typed and fail-closed.


from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, JsonValue, model_validator

from aec_bench.contracts.execution_program import (
    ExecutionProgramRef,
    ProgramNodeKind,
)
from aec_bench.contracts.harness_instance import ProgramOperationRef
from aec_bench.contracts.harness_kernel import (
    FrozenStrictModel,
)
from aec_bench.contracts.validators import NonEmptyStr


class OperationExecutionStatus(StrEnum):
    """Outcome of one trusted handler attempt."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"


class NodeExecutionStatus(StrEnum):
    """Observed runtime state for one compiled program node."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


class ProgramExecutionStatus(StrEnum):
    """Terminal status returned by the px runtime."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    STOPPED = "stopped"


class OperationResult(FrozenStrictModel):
    """Typed output returned by a trusted operation handler."""

    status: OperationExecutionStatus
    outputs: dict[str, JsonValue] = Field(default_factory=dict)
    error_code: NonEmptyStr | None = None
    error_message: NonEmptyStr | None = None

    @model_validator(mode="after")
    def validate_outcome(self) -> Self:
        if self.status is OperationExecutionStatus.SUCCEEDED and (
            self.error_code is not None or self.error_message is not None
        ):
            raise ValueError("successful operation results cannot contain errors")
        if self.status is OperationExecutionStatus.FAILED and self.error_code is None:
            raise ValueError("failed operation results require an error code")
        return self

    @classmethod
    def succeeded(cls, outputs: Mapping[str, JsonValue] | None = None) -> OperationResult:
        return cls(
            status=OperationExecutionStatus.SUCCEEDED,
            outputs={} if outputs is None else dict(outputs),
        )

    @classmethod
    def failed(cls, error_code: str, error_message: str | None = None) -> OperationResult:
        return cls(
            status=OperationExecutionStatus.FAILED,
            error_code=error_code,
            error_message=error_message,
        )


class OperationHandlerFailure(RuntimeError):
    """Typed failure a trusted handler may raise instead of returning a failed result."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        if not code.strip():
            raise ValueError("operation failure code must not be blank")
        self.code = code


class InputBindingLineage(FrozenStrictModel):
    """Content lineage for one literal, upstream port, or fanout-item argument."""

    argument_name: NonEmptyStr
    source_kind: Literal[
        "literal",
        "output",
        "fanout_item",
        "fanout_items",
        "verify_subject",
        "join_source",
        "branch_condition",
        "stop_result",
    ]
    source_node_id: NonEmptyStr | None = None
    source_output_port: NonEmptyStr | None = None
    fanout_index: int | None = Field(default=None, ge=0)
    value_sha256: str


class OperationLineage(FrozenStrictModel):
    """Compiled operation identity and Hx binding path used for one executable node."""

    operation_ref: ProgramOperationRef
    binding_ids: tuple[NonEmptyStr, ...]


class OperationAttemptEvidence(FrozenStrictModel):
    """Auditable evidence for one bounded handler invocation."""

    node_id: NonEmptyStr
    operation_ref: ProgramOperationRef
    attempt_index: int = Field(ge=1)
    fanout_index: int | None = Field(default=None, ge=0)
    arguments_sha256: str
    status: OperationExecutionStatus
    outputs_sha256: str | None = None
    error_code: NonEmptyStr | None = None
    error_message: NonEmptyStr | None = None
    recursive_calls: int = Field(default=0, ge=0)
    maximum_recursion_depth: int = Field(default=0, ge=0)


class NodeExecutionEvidence(FrozenStrictModel):
    """Per-node activation, data binding, operation lineage, attempts, and outputs."""

    node_id: NonEmptyStr
    kind: ProgramNodeKind
    status: NodeExecutionStatus
    dependency_node_ids: tuple[NonEmptyStr, ...]
    input_bindings: tuple[InputBindingLineage, ...] = ()
    operation_lineage: OperationLineage | None = None
    attempts: tuple[OperationAttemptEvidence, ...] = ()
    outputs: dict[str, JsonValue] = Field(default_factory=dict)
    selected_successor_node_id: NonEmptyStr | None = None
    error_code: NonEmptyStr | None = None
    error_message: NonEmptyStr | None = None


class ProgramExecutionResult(FrozenStrictModel):
    """Terminal px result with complete node evidence and consumed runtime budgets."""

    program_ref: ExecutionProgramRef
    status: ProgramExecutionStatus
    stop_node_id: NonEmptyStr | None = None
    result: JsonValue = None
    message: NonEmptyStr | None = None
    error_code: NonEmptyStr | None = None
    error_message: NonEmptyStr | None = None
    total_attempts: int = Field(ge=0)
    maximum_parallelism_observed: int = Field(ge=0)
    recursive_calls: int = Field(ge=0)
    maximum_recursion_depth: int = Field(ge=0)
    node_evidence: tuple[NodeExecutionEvidence, ...]

    @model_validator(mode="after")
    def validate_terminal_shape(self) -> Self:
        _validate_stop_reference(self)
        if self.status in {ProgramExecutionStatus.SUCCEEDED, ProgramExecutionStatus.STOPPED}:
            _validate_successful_terminal(self)
        else:
            _validate_failed_terminal(self)
        return self


def _failed_nodes(result: ProgramExecutionResult) -> tuple[NodeExecutionEvidence, ...]:
    return tuple(evidence for evidence in result.node_evidence if evidence.status is NodeExecutionStatus.FAILED)


def _validate_stop_reference(result: ProgramExecutionResult) -> None:
    reached_stop_ids = {
        evidence.node_id
        for evidence in result.node_evidence
        if evidence.kind is ProgramNodeKind.STOP and evidence.status is NodeExecutionStatus.SUCCEEDED
    }
    if result.stop_node_id is not None and result.stop_node_id not in reached_stop_ids:
        raise ValueError("program stop id must identify a reached stop node")


def _validate_successful_terminal(result: ProgramExecutionResult) -> None:
    if result.stop_node_id is None:
        raise ValueError("successful or stopped program results require a reached stop node")
    if result.error_code is not None or result.error_message is not None:
        raise ValueError("successful or stopped program results cannot contain error fields")
    if _failed_nodes(result):
        raise ValueError("successful or stopped program results cannot contain failed node evidence")


def _validate_failed_terminal(result: ProgramExecutionResult) -> None:
    if result.error_code is None:
        raise ValueError("failed program results require an error code")
    if result.stop_node_id is None and (result.result is not None or result.message is not None):
        raise ValueError("failed program results without a failed stop cannot contain terminal success data")
    if result.stop_node_id is None:
        return
    if result.error_code != "stop_failed":
        raise ValueError("failed stop results require the typed stop failure code")
    if _failed_nodes(result):
        raise ValueError("an earlier failed node must dominate a reached failed stop")
