# ABOUTME: Defines immutable execution-program DAGs compiled against a task-specific harness surface.
# ABOUTME: Models action, fanout, join, branch, verify, and stop nodes with bounded retry and recursion.

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, JsonValue, field_validator, model_validator

from aec_bench.contracts.harness_instance import HarnessInstanceRef, ProgramOperationRef
from aec_bench.contracts.harness_kernel import ContentAddressedModel, FrozenStrictModel, validate_sha256
from aec_bench.contracts.validators import NonEmptyStr


class ProgramNodeKind(StrEnum):
    """Executable control-flow primitives supported by the program contract."""

    ACTION = "action"
    FANOUT = "fanout"
    JOIN = "join"
    BRANCH = "branch"
    VERIFY = "verify"
    STOP = "stop"


class BranchOperator(StrEnum):
    """Closed comparison operators for deterministic branch evaluation."""

    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    GREATER_THAN = "greater_than"
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"
    LESS_THAN = "less_than"
    LESS_THAN_OR_EQUAL = "less_than_or_equal"
    CONTAINS = "contains"
    EXISTS = "exists"


class JoinStrategy(StrEnum):
    """Deterministic readiness rule for a join node."""

    ALL = "all"
    ANY = "any"
    FIRST_SUCCESS = "first_success"


class StopOutcome(StrEnum):
    """Explicit terminal outcome emitted by a stop node."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    STOPPED = "stopped"


class RetryPolicy(FrozenStrictModel):
    """Finite retry budget attached to an executable program node."""

    max_attempts: int = Field(default=1, ge=1, le=100)
    backoff_seconds: float = Field(default=0.0, ge=0.0, le=3_600.0)
    retry_on: tuple[NonEmptyStr, ...] = ()

    @field_validator("retry_on")
    @classmethod
    def validate_retry_on(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("retry conditions must be unique")
        if "*" in value:
            raise ValueError("wildcard retry conditions are not permitted")
        return value

    @model_validator(mode="after")
    def validate_retry_taxonomy(self) -> Self:
        if self.max_attempts > 1 and not self.retry_on:
            raise ValueError("multi-attempt retry policy requires explicit error codes")
        return self


class RecursionPolicy(FrozenStrictModel):
    """Finite recursion budget attached to a recursive action or fanout."""

    max_depth: int = Field(ge=1, le=32)
    max_calls: int = Field(ge=1, le=1_024)


class ProgramLimits(FrozenStrictModel):
    """Program-wide resource bounds enforced in addition to node-local policies."""

    max_nodes: int = Field(default=256, ge=1, le=10_000)
    max_parallelism: int = Field(default=32, ge=1, le=256)
    max_total_attempts: int = Field(default=256, ge=1, le=10_000)
    max_recursion_depth: int = Field(default=8, ge=0, le=32)
    max_recursive_calls: int = Field(default=128, ge=0, le=1_024)


class ProgramOutputRef(FrozenStrictModel):
    """Reference to one named output produced by an upstream node."""

    node_id: NonEmptyStr
    output_port: NonEmptyStr = "result"


class LiteralValue(FrozenStrictModel):
    """JSON literal supplied directly to an operation argument."""

    kind: Literal["literal"] = "literal"
    value: JsonValue


class OutputValue(FrozenStrictModel):
    """Operation argument sourced from a declared upstream dependency."""

    kind: Literal["output"] = "output"
    ref: ProgramOutputRef


ProgramValue = Annotated[LiteralValue | OutputValue, Field(discriminator="kind")]


class ProgramArgument(FrozenStrictModel):
    """Named operation argument with an explicit literal or upstream source."""

    name: NonEmptyStr
    value: ProgramValue


class BranchCondition(FrozenStrictModel):
    """Closed condition evaluated over one upstream node output."""

    value: ProgramOutputRef
    operator: BranchOperator
    expected: JsonValue = None


class ProgramNodeBase(FrozenStrictModel):
    """Common identity and incoming dependency edges for every program node."""

    node_id: NonEmptyStr
    kind: ProgramNodeKind
    depends_on: tuple[NonEmptyStr, ...] = ()

    @model_validator(mode="after")
    def validate_dependencies(self) -> Self:
        if len(self.depends_on) != len(set(self.depends_on)):
            raise ValueError(f"program node {self.node_id!r} dependencies must be unique")
        if self.node_id in self.depends_on:
            raise ValueError(f"program node {self.node_id!r} cannot depend on itself")
        return self


class ActionNode(ProgramNodeBase):
    """Invoke one operation exported by the target harness surface."""

    kind: Literal[ProgramNodeKind.ACTION] = ProgramNodeKind.ACTION
    operation_id: NonEmptyStr
    arguments: tuple[ProgramArgument, ...] = ()
    retry: RetryPolicy | None = None
    recursion: RecursionPolicy | None = None

    @field_validator("arguments")
    @classmethod
    def validate_arguments(cls, value: tuple[ProgramArgument, ...]) -> tuple[ProgramArgument, ...]:
        _validate_unique_argument_names(value)
        return value


class FanoutNode(ProgramNodeBase):
    """Invoke one operation independently for every item from an upstream collection."""

    kind: Literal[ProgramNodeKind.FANOUT] = ProgramNodeKind.FANOUT
    operation_id: NonEmptyStr
    items: ProgramOutputRef
    item_argument: NonEmptyStr
    arguments: tuple[ProgramArgument, ...] = ()
    max_parallelism: int = Field(default=1, ge=1, le=256)
    retry: RetryPolicy | None = None
    recursion: RecursionPolicy | None = None

    @field_validator("arguments")
    @classmethod
    def validate_arguments(cls, value: tuple[ProgramArgument, ...]) -> tuple[ProgramArgument, ...]:
        _validate_unique_argument_names(value)
        return value


class JoinNode(ProgramNodeBase):
    """Synchronize multiple upstream outputs under a declared readiness strategy."""

    kind: Literal[ProgramNodeKind.JOIN] = ProgramNodeKind.JOIN
    sources: tuple[ProgramOutputRef, ...] = Field(min_length=2)
    strategy: JoinStrategy = JoinStrategy.ALL

    @field_validator("sources")
    @classmethod
    def validate_sources(cls, value: tuple[ProgramOutputRef, ...]) -> tuple[ProgramOutputRef, ...]:
        refs = [(source.node_id, source.output_port) for source in value]
        if len(refs) != len(set(refs)):
            raise ValueError("join sources must be unique")
        return value


class BranchNode(ProgramNodeBase):
    """Route execution to one of two explicit successor nodes."""

    kind: Literal[ProgramNodeKind.BRANCH] = ProgramNodeKind.BRANCH
    condition: BranchCondition
    true_node_id: NonEmptyStr
    false_node_id: NonEmptyStr

    @model_validator(mode="after")
    def validate_targets(self) -> Self:
        if self.true_node_id == self.false_node_id:
            raise ValueError("branch true and false targets must differ")
        if self.node_id in {self.true_node_id, self.false_node_id}:
            raise ValueError("branch cannot target itself")
        return self


class VerifyNode(ProgramNodeBase):
    """Invoke a harness-exported verifier over an upstream output."""

    kind: Literal[ProgramNodeKind.VERIFY] = ProgramNodeKind.VERIFY
    operation_id: NonEmptyStr
    subject: ProgramOutputRef
    arguments: tuple[ProgramArgument, ...] = ()
    retry: RetryPolicy | None = None

    @field_validator("arguments")
    @classmethod
    def validate_arguments(cls, value: tuple[ProgramArgument, ...]) -> tuple[ProgramArgument, ...]:
        _validate_unique_argument_names(value)
        return value


class StopNode(ProgramNodeBase):
    """Terminate one program path with an explicit outcome and optional result."""

    kind: Literal[ProgramNodeKind.STOP] = ProgramNodeKind.STOP
    outcome: StopOutcome
    result: ProgramOutputRef | None = None
    message: NonEmptyStr | None = None


ProgramNode = Annotated[
    ActionNode | FanoutNode | JoinNode | BranchNode | VerifyNode | StopNode,
    Field(discriminator="kind"),
]


class ExecutionProgramRef(FrozenStrictModel):
    """Content-pinned reference to one proposed or compiled execution program."""

    program_id: NonEmptyStr
    version: NonEmptyStr
    content_sha256: str

    @field_validator("content_sha256")
    @classmethod
    def validate_content_sha256(cls, value: str) -> str:
        return validate_sha256(value)


class ExecutionProgram(ContentAddressedModel):
    """Immutable px proposal expressed as a validated full control-flow DAG."""

    program_id: NonEmptyStr
    version: NonEmptyStr
    harness_ref: HarnessInstanceRef
    nodes: tuple[ProgramNode, ...]
    limits: ProgramLimits = Field(default_factory=ProgramLimits)

    @model_validator(mode="after")
    def validate_program(self) -> Self:
        _validate_program_graph(self.nodes, self.limits)
        return self

    @property
    def ref(self) -> ExecutionProgramRef:
        return ExecutionProgramRef(
            program_id=self.program_id,
            version=self.version,
            content_sha256=self.content_sha256,
        )


class CompiledExecutionProgram(ContentAddressedModel):
    """Immutable px accepted against one exact Hx program surface."""

    program_id: NonEmptyStr
    version: NonEmptyStr
    harness_ref: HarnessInstanceRef
    source_program_sha256: str
    surface_sha256: str
    nodes: tuple[ProgramNode, ...]
    limits: ProgramLimits
    topological_order: tuple[NonEmptyStr, ...]
    operation_refs: tuple[ProgramOperationRef, ...]

    @field_validator("source_program_sha256", "surface_sha256")
    @classmethod
    def validate_sha256_fields(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_compiled_program(self) -> Self:
        _validate_program_graph(self.nodes, self.limits)
        _validate_topological_order(self.nodes, self.topological_order)
        _validate_operation_refs(self.nodes, self.operation_refs)
        return self

    @property
    def ref(self) -> ExecutionProgramRef:
        return ExecutionProgramRef(
            program_id=self.program_id,
            version=self.version,
            content_sha256=self.content_sha256,
        )


def _validate_program_graph(nodes: tuple[ProgramNode, ...], limits: ProgramLimits) -> None:
    _validate_program_size(nodes, limits)
    nodes_by_id = _index_program_nodes(nodes)
    dependencies = {node.node_id: set(node.depends_on) for node in nodes}
    _validate_node_relationships(nodes, nodes_by_id, dependencies)
    _validate_acyclic(dependencies)
    _validate_terminals(nodes, dependencies)
    _validate_program_limits(nodes, limits)


def _validate_program_size(nodes: tuple[ProgramNode, ...], limits: ProgramLimits) -> None:
    if not nodes:
        raise ValueError("execution program must include at least one node")
    if len(nodes) > limits.max_nodes:
        raise ValueError(f"program node count {len(nodes)} exceeds program limit {limits.max_nodes}")


def _index_program_nodes(nodes: tuple[ProgramNode, ...]) -> dict[str, ProgramNode]:
    node_ids = [node.node_id for node in nodes]
    if len(node_ids) != len(set(node_ids)):
        raise ValueError("program node ids must be unique")
    return {node.node_id: node for node in nodes}


def _validate_node_relationships(
    nodes: tuple[ProgramNode, ...],
    nodes_by_id: dict[str, ProgramNode],
    dependencies: dict[str, set[str]],
) -> None:
    known_ids = set(nodes_by_id)
    for node in nodes:
        _validate_declared_dependencies(node, dependencies[node.node_id], known_ids)
        _validate_declared_references(node, dependencies[node.node_id])
        if isinstance(node, BranchNode):
            _validate_branch_targets(node, nodes_by_id)


def _validate_declared_dependencies(
    node: ProgramNode,
    dependencies: set[str],
    known_ids: set[str],
) -> None:
    unknown_dependencies = sorted(dependencies - known_ids)
    if unknown_dependencies:
        raise ValueError(f"program node {node.node_id!r} has unknown dependencies: " + ", ".join(unknown_dependencies))


def _validate_declared_references(node: ProgramNode, dependencies: set[str]) -> None:
    hidden_references = sorted(_referenced_node_ids(node) - dependencies)
    if hidden_references:
        raise ValueError(
            f"program node {node.node_id!r} references nodes that are not declared dependencies: "
            + ", ".join(hidden_references)
        )


def _validate_branch_targets(node: BranchNode, nodes_by_id: dict[str, ProgramNode]) -> None:
    for target_id in (node.true_node_id, node.false_node_id):
        target = nodes_by_id.get(target_id)
        if target is None:
            raise ValueError(f"branch node {node.node_id!r} has unknown target: {target_id}")
        if node.node_id not in target.depends_on:
            raise ValueError(f"branch target {target_id!r} must depend on branch {node.node_id!r}")


def _validate_acyclic(dependencies: dict[str, set[str]]) -> None:
    remaining = {node_id: set(node_dependencies) for node_id, node_dependencies in dependencies.items()}
    while remaining:
        ready = {node_id for node_id, node_dependencies in remaining.items() if not node_dependencies}
        if not ready:
            raise ValueError("program graph must be acyclic")
        for node_id in ready:
            del remaining[node_id]
        for node_dependencies in remaining.values():
            node_dependencies.difference_update(ready)


def _validate_terminals(nodes: tuple[ProgramNode, ...], dependencies: dict[str, set[str]]) -> None:
    nodes_with_dependents = {
        dependency for node_dependencies in dependencies.values() for dependency in node_dependencies
    }
    invalid_terminals = sorted(
        node.node_id for node in nodes if node.node_id not in nodes_with_dependents and not isinstance(node, StopNode)
    )
    if invalid_terminals:
        raise ValueError("terminal nodes must be stop nodes: " + ", ".join(invalid_terminals))


def _validate_program_limits(nodes: tuple[ProgramNode, ...], limits: ProgramLimits) -> None:
    retry_policies = [
        node.retry
        for node in nodes
        if isinstance(node, ActionNode | FanoutNode | VerifyNode) and node.retry is not None
    ]
    total_attempts = sum(policy.max_attempts for policy in retry_policies)
    if total_attempts > limits.max_total_attempts:
        raise ValueError(f"retry attempts {total_attempts} exceed program limit {limits.max_total_attempts}")

    recursive_nodes = [
        node for node in nodes if isinstance(node, ActionNode | FanoutNode) and node.recursion is not None
    ]
    for recursive_node in recursive_nodes:
        assert recursive_node.recursion is not None
        if recursive_node.recursion.max_depth > limits.max_recursion_depth:
            raise ValueError(
                f"recursion depth {recursive_node.recursion.max_depth} "
                f"exceeds program limit {limits.max_recursion_depth}"
            )
    recursive_calls = sum(node.recursion.max_calls for node in recursive_nodes if node.recursion is not None)
    if recursive_calls > limits.max_recursive_calls:
        raise ValueError(f"recursive calls {recursive_calls} exceed program limit {limits.max_recursive_calls}")

    for candidate_node in nodes:
        if isinstance(candidate_node, FanoutNode) and candidate_node.max_parallelism > limits.max_parallelism:
            raise ValueError(
                f"fanout parallelism {candidate_node.max_parallelism} exceeds program limit {limits.max_parallelism}"
            )


def _validate_topological_order(nodes: tuple[ProgramNode, ...], order: tuple[str, ...]) -> None:
    node_ids = {node.node_id for node in nodes}
    if len(order) != len(set(order)) or set(order) != node_ids:
        raise ValueError("topological_order must contain every program node exactly once")

    positions = {node_id: index for index, node_id in enumerate(order)}
    for node in nodes:
        misplaced = [dependency for dependency in node.depends_on if positions[dependency] > positions[node.node_id]]
        if misplaced:
            dependency = min(misplaced, key=positions.__getitem__)
            raise ValueError(f"topological_order places dependency {dependency!r} after {node.node_id!r}")


def _validate_operation_refs(
    nodes: tuple[ProgramNode, ...],
    operation_refs: tuple[ProgramOperationRef, ...],
) -> None:
    invoked_operation_ids = {
        node.operation_id for node in nodes if isinstance(node, ActionNode | FanoutNode | VerifyNode)
    }
    reference_ids = [reference.operation_id for reference in operation_refs]
    if len(reference_ids) != len(set(reference_ids)) or set(reference_ids) != invoked_operation_ids:
        raise ValueError("operation_refs must resolve every invoked operation exactly once")


def _referenced_node_ids(node: ProgramNode) -> set[str]:
    references: set[str] = set()
    if isinstance(node, ActionNode | FanoutNode | VerifyNode):
        references.update(_argument_reference_ids(node.arguments))
    if isinstance(node, FanoutNode):
        references.add(node.items.node_id)
    elif isinstance(node, JoinNode):
        references.update(source.node_id for source in node.sources)
    elif isinstance(node, BranchNode):
        references.add(node.condition.value.node_id)
    elif isinstance(node, VerifyNode):
        references.add(node.subject.node_id)
    elif isinstance(node, StopNode) and node.result is not None:
        references.add(node.result.node_id)
    return references


def _argument_reference_ids(arguments: tuple[ProgramArgument, ...]) -> set[str]:
    return {argument.value.ref.node_id for argument in arguments if isinstance(argument.value, OutputValue)}


def _validate_unique_argument_names(arguments: tuple[ProgramArgument, ...]) -> None:
    names = [argument.name for argument in arguments]
    if len(names) != len(set(names)):
        raise ValueError("program argument names must be unique")
