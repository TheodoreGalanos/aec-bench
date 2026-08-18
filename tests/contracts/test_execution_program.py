# ABOUTME: Tests the typed execution-program DAG spanning action, fanout, join, branch, verify, and stop nodes.
# ABOUTME: Verifies dependency integrity, explicit terminal paths, and bounded retry and recursion metadata.

import pytest
from pydantic import ValidationError

from aec_bench.contracts.execution_program import (
    ActionNode,
    BranchCondition,
    BranchNode,
    BranchOperator,
    CompiledExecutionProgram,
    ExecutionProgram,
    ExecutionProgramRef,
    FanoutNode,
    JoinNode,
    LiteralValue,
    OutputValue,
    ProgramArgument,
    ProgramLimits,
    ProgramNode,
    ProgramOutputRef,
    RecursionPolicy,
    RetryPolicy,
    StopNode,
    StopOutcome,
    VerifyNode,
)
from aec_bench.contracts.harness_instance import HarnessInstanceRef, ProgramOperationRef


def _harness_ref() -> HarnessInstanceRef:
    return HarnessInstanceRef(instance_id="hx-trace-diagnosis")


def _operation_refs() -> tuple[ProgramOperationRef, ...]:
    return (
        ProgramOperationRef(operation_id="load_traces.v1"),
        ProgramOperationRef(operation_id="review_trace.v1"),
        ProgramOperationRef(operation_id="verify_repair.v1"),
    )


def _full_dag_nodes() -> tuple[
    ActionNode,
    FanoutNode,
    JoinNode,
    BranchNode,
    VerifyNode,
    StopNode,
    StopNode,
]:
    load = ActionNode(
        node_id="load",
        operation_id="load_traces.v1",
        arguments=(ProgramArgument(name="scope", value=LiteralValue(value="failed")),),
        retry=RetryPolicy(
            max_attempts=2,
            backoff_seconds=0.5,
            retry_on=("trace_load_transient",),
        ),
        recursion=RecursionPolicy(max_depth=2, max_calls=8),
    )
    fanout = FanoutNode(
        node_id="review",
        depends_on=("load",),
        operation_id="review_trace.v1",
        items=ProgramOutputRef(node_id="load", output_port="traces"),
        item_argument="trace",
        max_parallelism=4,
        retry=RetryPolicy(max_attempts=3, retry_on=("trace_review_transient",)),
    )
    join = JoinNode(
        node_id="synthesize",
        depends_on=("load", "review"),
        sources=(
            ProgramOutputRef(node_id="load", output_port="trace_index"),
            ProgramOutputRef(node_id="review", output_port="findings"),
        ),
    )
    branch = BranchNode(
        node_id="quality-gate",
        depends_on=("synthesize",),
        condition=BranchCondition(
            value=ProgramOutputRef(node_id="synthesize", output_port="has_evidence"),
            operator=BranchOperator.EQUALS,
            expected=True,
        ),
        true_node_id="verify",
        false_node_id="stop-insufficient",
    )
    verify = VerifyNode(
        node_id="verify",
        depends_on=("quality-gate", "synthesize"),
        operation_id="verify_repair.v1",
        subject=ProgramOutputRef(node_id="synthesize", output_port="repair_plan"),
        retry=RetryPolicy(max_attempts=2, retry_on=("verification_transient",)),
    )
    stop_success = StopNode(
        node_id="stop-success",
        depends_on=("verify",),
        outcome=StopOutcome.SUCCEEDED,
        result=ProgramOutputRef(node_id="verify", output_port="verified_plan"),
    )
    stop_insufficient = StopNode(
        node_id="stop-insufficient",
        depends_on=("quality-gate",),
        outcome=StopOutcome.STOPPED,
        message="Insufficient evidence for a repair proposal.",
    )
    return load, fanout, join, branch, verify, stop_success, stop_insufficient


def test_execution_program_accepts_the_full_typed_dag() -> None:
    program = ExecutionProgram(
        program_id="px-trace-diagnosis",
        version="1.0.0",
        harness_ref=_harness_ref(),
        nodes=_full_dag_nodes(),
        limits=ProgramLimits(
            max_nodes=32,
            max_parallelism=8,
            max_total_attempts=32,
            max_recursion_depth=4,
            max_recursive_calls=32,
        ),
    )

    assert {node.kind.value for node in program.nodes} == {
        "action",
        "fanout",
        "join",
        "branch",
        "verify",
        "stop",
    }
    assert program.ref == ExecutionProgramRef(program_id=program.program_id, version=program.version)
    assert "content_sha256" not in program.model_dump(mode="json")


def test_execution_program_rejects_a_cycle() -> None:
    first = ActionNode(node_id="first", depends_on=("second",), operation_id="first.v1")
    second = StopNode(node_id="second", depends_on=("first",), outcome=StopOutcome.SUCCEEDED)

    with pytest.raises(ValidationError, match="program graph must be acyclic"):
        ExecutionProgram(
            program_id="px-cycle",
            version="1.0.0",
            harness_ref=_harness_ref(),
            nodes=(first, second),
        )


def test_execution_program_requires_data_references_to_be_dependencies() -> None:
    load = ActionNode(node_id="load", operation_id="load.v1")
    stop = StopNode(
        node_id="stop",
        outcome=StopOutcome.SUCCEEDED,
        result=ProgramOutputRef(node_id="load", output_port="result"),
    )

    with pytest.raises(ValidationError, match="references nodes that are not declared dependencies: load"):
        ExecutionProgram(
            program_id="px-hidden-edge",
            version="1.0.0",
            harness_ref=_harness_ref(),
            nodes=(load, stop),
        )


def test_execution_program_requires_branch_targets_to_depend_on_the_branch() -> None:
    source = ActionNode(node_id="source", operation_id="source.v1")
    branch = BranchNode(
        node_id="branch",
        depends_on=("source",),
        condition=BranchCondition(
            value=ProgramOutputRef(node_id="source", output_port="ok"),
            operator=BranchOperator.EQUALS,
            expected=True,
        ),
        true_node_id="yes",
        false_node_id="no",
    )
    yes = StopNode(node_id="yes", depends_on=("source",), outcome=StopOutcome.SUCCEEDED)
    no = StopNode(node_id="no", depends_on=("branch",), outcome=StopOutcome.FAILED)

    with pytest.raises(ValidationError, match="branch target 'yes' must depend on branch 'branch'"):
        ExecutionProgram(
            program_id="px-invalid-branch",
            version="1.0.0",
            harness_ref=_harness_ref(),
            nodes=(source, branch, yes, no),
        )


def test_execution_program_preserves_relationship_error_order() -> None:
    source = ActionNode(node_id="source", operation_id="source.v1")
    branch = BranchNode(
        node_id="branch",
        depends_on=("missing-dependency",),
        condition=BranchCondition(
            value=ProgramOutputRef(node_id="source", output_port="ok"),
            operator=BranchOperator.EQUALS,
            expected=True,
        ),
        true_node_id="missing-yes",
        false_node_id="missing-no",
    )

    with pytest.raises(
        ValidationError,
        match="program node 'branch' has unknown dependencies: missing-dependency",
    ):
        ExecutionProgram(
            program_id="px-ordered-errors",
            version="1.0.0",
            harness_ref=_harness_ref(),
            nodes=(source, branch),
        )


def test_execution_program_requires_explicit_stop_terminals() -> None:
    with pytest.raises(ValidationError, match="terminal nodes must be stop nodes: action"):
        ExecutionProgram(
            program_id="px-no-stop",
            version="1.0.0",
            harness_ref=_harness_ref(),
            nodes=(ActionNode(node_id="action", operation_id="action.v1"),),
        )


def test_retry_recursion_and_fanout_are_bounded_by_program_limits() -> None:
    nodes: list[ProgramNode] = list(_full_dag_nodes())
    nodes[0] = ActionNode(
        node_id="load",
        operation_id="load_traces.v1",
        recursion=RecursionPolicy(max_depth=5, max_calls=8),
    )

    with pytest.raises(ValidationError, match="recursion depth 5 exceeds program limit 4"):
        ExecutionProgram(
            program_id="px-over-budget",
            version="1.0.0",
            harness_ref=_harness_ref(),
            nodes=tuple(nodes),
            limits=ProgramLimits(max_recursion_depth=4),
        )

    with pytest.raises(ValidationError):
        RetryPolicy(max_attempts=0)

    with pytest.raises(ValidationError):
        RecursionPolicy(max_depth=33, max_calls=1)


def test_multi_attempt_retry_requires_explicit_error_codes() -> None:
    with pytest.raises(ValidationError, match="multi-attempt retry policy requires explicit error codes"):
        RetryPolicy(max_attempts=2)

    with pytest.raises(ValidationError, match="wildcard retry conditions are not permitted"):
        RetryPolicy(max_attempts=2, retry_on=("*",))

    assert RetryPolicy(max_attempts=1).retry_on == ()


def test_compiled_program_pins_source_surface_and_topological_order() -> None:
    source = ExecutionProgram(
        program_id="px-trace-diagnosis",
        version="1.0.0",
        harness_ref=_harness_ref(),
        nodes=_full_dag_nodes(),
    )
    order = (
        "load",
        "review",
        "synthesize",
        "quality-gate",
        "verify",
        "stop-success",
        "stop-insufficient",
    )
    compiled = CompiledExecutionProgram(
        program_id=source.program_id,
        version=source.version,
        harness_ref=source.harness_ref,
        source_program_ref=source.ref,
        surface_id="trace-diagnosis-surface",
        nodes=source.nodes,
        limits=source.limits,
        topological_order=order,
        operation_refs=_operation_refs(),
    )

    assert compiled.ref == source.ref
    assert "content_sha256" not in compiled.model_dump(mode="json")

    with pytest.raises(ValidationError, match="topological_order places dependency 'synthesize' after 'verify'"):
        CompiledExecutionProgram(
            program_id=source.program_id,
            version=source.version,
            harness_ref=source.harness_ref,
            source_program_ref=source.ref,
            surface_id="trace-diagnosis-surface",
            nodes=source.nodes,
            limits=source.limits,
            operation_refs=_operation_refs(),
            topological_order=(
                "load",
                "review",
                "verify",
                "synthesize",
                "quality-gate",
                "stop-success",
                "stop-insufficient",
            ),
        )


def test_program_argument_names_must_be_unique_within_an_operation_call() -> None:
    with pytest.raises(ValidationError, match="program argument names must be unique"):
        ActionNode(
            node_id="duplicate-arguments",
            operation_id="load.v1",
            arguments=(
                ProgramArgument(name="scope", value=LiteralValue(value="failed")),
                ProgramArgument(name="scope", value=LiteralValue(value="all")),
            ),
        )


def test_compiled_program_requires_one_content_pinned_ref_per_invoked_operation() -> None:
    source = ExecutionProgram(
        program_id="px-operation-resolution",
        version="1.0.0",
        harness_ref=_harness_ref(),
        nodes=(
            ActionNode(node_id="load", operation_id="load.v1"),
            StopNode(node_id="stop", depends_on=("load",), outcome=StopOutcome.SUCCEEDED),
        ),
    )

    with pytest.raises(ValidationError, match="operation_refs must resolve every invoked operation exactly once"):
        CompiledExecutionProgram(
            program_id=source.program_id,
            version=source.version,
            harness_ref=source.harness_ref,
            source_program_ref=source.ref,
            surface_id="trace-diagnosis-surface",
            nodes=source.nodes,
            limits=source.limits,
            topological_order=("load", "stop"),
            operation_refs=(ProgramOperationRef(operation_id="other.v1"),),
        )


def test_output_arguments_are_part_of_dependency_validation() -> None:
    source = ActionNode(node_id="source", operation_id="source.v1")
    consumer = ActionNode(
        node_id="consumer",
        operation_id="consumer.v1",
        arguments=(
            ProgramArgument(
                name="value",
                value=OutputValue(ref=ProgramOutputRef(node_id="source", output_port="result")),
            ),
        ),
    )
    stop = StopNode(node_id="stop", depends_on=("consumer",), outcome=StopOutcome.SUCCEEDED)

    with pytest.raises(ValidationError, match="references nodes that are not declared dependencies: source"):
        ExecutionProgram(
            program_id="px-hidden-argument-edge",
            version="1.0.0",
            harness_ref=_harness_ref(),
            nodes=(source, consumer, stop),
        )
