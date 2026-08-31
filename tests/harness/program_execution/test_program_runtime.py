# ABOUTME: Exercises the trusted executable runtime for compiled px DAGs.
# ABOUTME: Covers routing, fanout joins, retries, lineage, ports, and hard runtime budgets.

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

import pytest
from pydantic import JsonValue, ValidationError

from aec_bench.contracts.execution_program import (
    ActionNode,
    BranchCondition,
    BranchNode,
    BranchOperator,
    CompiledExecutionProgram,
    ExecutionProgramRef,
    FanoutNode,
    JoinNode,
    JoinStrategy,
    LiteralValue,
    OutputValue,
    ProgramArgument,
    ProgramLimits,
    ProgramNode,
    ProgramNodeKind,
    ProgramOutputRef,
    RecursionPolicy,
    RetryPolicy,
    StopNode,
    StopOutcome,
    VerifyNode,
)
from aec_bench.contracts.harness_instance import HarnessInstanceRef, ProgramOperationRef
from aec_bench.harness.program_execution import (
    NodeExecutionEvidence,
    NodeExecutionStatus,
    OperationExecutionContext,
    OperationHandler,
    OperationRegistration,
    OperationRegistry,
    OperationResult,
    ProgramExecutionResult,
    ProgramExecutionStatus,
    execute_program,
)


def _ref(operation_id: str) -> ProgramOperationRef:
    return ProgramOperationRef(operation_id=operation_id)


def _registration(
    operation_id: str,
    handler: OperationHandler,
    *,
    max_parallelism: int = 1,
) -> OperationRegistration:
    return OperationRegistration(
        reference=_ref(operation_id),
        binding_ids=(f"binding.{operation_id}",),
        handler=handler,
        max_parallelism=max_parallelism,
    )


def _program(
    nodes: tuple[ProgramNode, ...],
    operation_refs: tuple[ProgramOperationRef, ...],
    *,
    limits: ProgramLimits | None = None,
) -> CompiledExecutionProgram:
    return CompiledExecutionProgram(
        program_id="px-runtime-test",
        version="1.0.0",
        harness_ref=HarnessInstanceRef(instance_id="hx-runtime-test"),
        source_program_ref=ExecutionProgramRef(program_id="source-px-runtime-test", version="1.0.0"),
        surface_id="surface-runtime-test",
        nodes=nodes,
        limits=limits or ProgramLimits(max_total_attempts=64, max_parallelism=8),
        topological_order=tuple(node.node_id for node in nodes),
        operation_refs=operation_refs,
    )


def _evidence(result_node_id: str, result: ProgramExecutionResult) -> NodeExecutionEvidence:
    return next(item for item in result.node_evidence if item.node_id == result_node_id)


def test_executes_actions_verify_and_stop_with_port_and_binding_lineage() -> None:
    def load(arguments: Mapping[str, JsonValue], context: OperationExecutionContext) -> OperationResult:
        assert context.node_id == "load"
        return OperationResult.succeeded({"numbers": arguments["numbers"]})

    def total(arguments: Mapping[str, JsonValue], context: OperationExecutionContext) -> OperationResult:
        del context
        numbers = arguments["numbers"]
        assert isinstance(numbers, list)
        typed_numbers: list[int] = []
        for number in numbers:
            assert isinstance(number, int)
            typed_numbers.append(number)
        return OperationResult.succeeded({"total": sum(typed_numbers)})

    def verify(arguments: Mapping[str, JsonValue], context: OperationExecutionContext) -> OperationResult:
        del context
        subject = arguments["subject"]
        minimum = arguments["minimum"]
        assert isinstance(subject, int)
        assert isinstance(minimum, int)
        if subject < minimum:
            return OperationResult.failed("below_minimum", "Total did not meet the threshold.")
        return OperationResult.succeeded({"verified_total": subject})

    registrations = (
        _registration("load.v1", load),
        _registration("total.v1", total),
        _registration("verify.v1", verify),
    )
    nodes: tuple[ProgramNode, ...] = (
        ActionNode(
            node_id="load",
            operation_id="load.v1",
            arguments=(ProgramArgument(name="numbers", value=LiteralValue(value=[2, 3])),),
        ),
        ActionNode(
            node_id="total",
            depends_on=("load",),
            operation_id="total.v1",
            arguments=(
                ProgramArgument(
                    name="numbers",
                    value=OutputValue(ref=ProgramOutputRef(node_id="load", output_port="numbers")),
                ),
            ),
        ),
        VerifyNode(
            node_id="verify",
            depends_on=("total",),
            operation_id="verify.v1",
            subject=ProgramOutputRef(node_id="total", output_port="total"),
            arguments=(ProgramArgument(name="minimum", value=LiteralValue(value=5)),),
        ),
        StopNode(
            node_id="stop",
            depends_on=("verify",),
            outcome=StopOutcome.SUCCEEDED,
            result=ProgramOutputRef(node_id="verify", output_port="verified_total"),
        ),
    )

    result = execute_program(
        _program(nodes, tuple(registration.reference for registration in registrations)),
        OperationRegistry(registrations),
    )

    total_evidence = _evidence("total", result)
    verify_evidence = _evidence("verify", result)
    assert result.status is ProgramExecutionStatus.SUCCEEDED
    assert result.result == 5
    assert result.total_attempts == 3
    assert total_evidence.operation_lineage is not None
    assert total_evidence.operation_lineage.binding_ids == ("binding.total.v1",)
    assert total_evidence.input_bindings[0].source_node_id == "load"
    assert total_evidence.input_bindings[0].source_output_port == "numbers"
    assert [binding.argument_name for binding in verify_evidence.input_bindings] == [
        "minimum",
        "subject",
    ]


def test_branch_executes_only_the_selected_successor() -> None:
    true_path_calls: list[str] = []

    def decide(arguments: Mapping[str, JsonValue], context: OperationExecutionContext) -> OperationResult:
        del arguments, context
        return OperationResult.succeeded({"approved": False})

    def true_path(arguments: Mapping[str, JsonValue], context: OperationExecutionContext) -> OperationResult:
        del arguments, context
        true_path_calls.append("called")
        return OperationResult.succeeded({"result": "unexpected"})

    registrations = (
        _registration("decide.v1", decide),
        _registration("true-path.v1", true_path),
    )
    nodes: tuple[ProgramNode, ...] = (
        ActionNode(node_id="decide", operation_id="decide.v1"),
        BranchNode(
            node_id="route",
            depends_on=("decide",),
            condition=BranchCondition(
                value=ProgramOutputRef(node_id="decide", output_port="approved"),
                operator=BranchOperator.EQUALS,
                expected=True,
            ),
            true_node_id="true-path",
            false_node_id="stop-declined",
        ),
        ActionNode(
            node_id="true-path",
            depends_on=("route",),
            operation_id="true-path.v1",
        ),
        StopNode(
            node_id="stop-approved",
            depends_on=("true-path",),
            outcome=StopOutcome.SUCCEEDED,
        ),
        StopNode(
            node_id="stop-declined",
            depends_on=("route",),
            outcome=StopOutcome.STOPPED,
            message="Not approved.",
        ),
    )

    result = execute_program(
        _program(nodes, tuple(registration.reference for registration in registrations)),
        OperationRegistry(registrations),
    )

    assert result.status is ProgramExecutionStatus.STOPPED
    assert result.stop_node_id == "stop-declined"
    assert true_path_calls == []
    assert _evidence("true-path", result).status is NodeExecutionStatus.SKIPPED
    assert _evidence("true-path", result).error_code == "branch_not_selected"
    assert _evidence("stop-approved", result).status is NodeExecutionStatus.SKIPPED


@pytest.mark.parametrize(
    ("strategy", "expected"),
    [
        (JoinStrategy.ALL, ["batch", [1, 4, 9]]),
        (JoinStrategy.ANY, ["batch", [1, 4, 9]]),
        (JoinStrategy.FIRST_SUCCESS, "batch"),
    ],
)
def test_fanout_and_each_join_strategy(
    strategy: JoinStrategy,
    expected: JsonValue,
) -> None:
    def source(arguments: Mapping[str, JsonValue], context: OperationExecutionContext) -> OperationResult:
        del arguments, context
        return OperationResult.succeeded({"items": [1, 2, 3], "label": "batch"})

    def square(arguments: Mapping[str, JsonValue], context: OperationExecutionContext) -> OperationResult:
        number = arguments["number"]
        assert isinstance(number, int)
        assert context.fanout_index is not None
        return OperationResult.succeeded({"value": number * number})

    registrations = (
        _registration("source.v1", source),
        _registration("square.v1", square, max_parallelism=2),
    )
    nodes: tuple[ProgramNode, ...] = (
        ActionNode(node_id="source", operation_id="source.v1"),
        FanoutNode(
            node_id="square",
            depends_on=("source",),
            operation_id="square.v1",
            items=ProgramOutputRef(node_id="source", output_port="items"),
            item_argument="number",
            max_parallelism=2,
        ),
        JoinNode(
            node_id="join",
            depends_on=("source", "square"),
            sources=(
                ProgramOutputRef(node_id="source", output_port="label"),
                ProgramOutputRef(node_id="square", output_port="value"),
            ),
            strategy=strategy,
        ),
        StopNode(
            node_id="stop",
            depends_on=("join",),
            outcome=StopOutcome.SUCCEEDED,
            result=ProgramOutputRef(node_id="join", output_port="result"),
        ),
    )

    result = execute_program(
        _program(nodes, tuple(registration.reference for registration in registrations)),
        OperationRegistry(registrations),
    )

    assert result.status is ProgramExecutionStatus.SUCCEEDED
    assert result.result == expected
    assert _evidence("square", result).outputs == {"value": [1, 4, 9]}
    assert result.maximum_parallelism_observed <= 2


def test_retries_declared_failures_then_succeeds() -> None:
    class FlakyHandler:
        def __init__(self) -> None:
            self.calls = 0

        def __call__(
            self,
            arguments: Mapping[str, JsonValue],
            context: OperationExecutionContext,
        ) -> OperationResult:
            del arguments, context
            self.calls += 1
            if self.calls == 1:
                return OperationResult.failed("transient", "Please retry.")
            return OperationResult.succeeded({"result": "recovered"})

    handler = FlakyHandler()
    registration = _registration("flaky.v1", handler)
    nodes: tuple[ProgramNode, ...] = (
        ActionNode(
            node_id="flaky",
            operation_id="flaky.v1",
            retry=RetryPolicy(max_attempts=3, retry_on=("transient",)),
        ),
        StopNode(
            node_id="stop",
            depends_on=("flaky",),
            outcome=StopOutcome.SUCCEEDED,
            result=ProgramOutputRef(node_id="flaky"),
        ),
    )

    result = execute_program(
        _program(nodes, (registration.reference,)),
        OperationRegistry((registration,)),
    )

    attempts = _evidence("flaky", result).attempts
    assert result.status is ProgramExecutionStatus.SUCCEEDED
    assert result.result == "recovered"
    assert handler.calls == 2
    assert [attempt.error_code for attempt in attempts] == ["transient", None]


def test_does_not_retry_an_unknown_failure_code() -> None:
    calls = 0

    def fail_unknown(
        arguments: Mapping[str, JsonValue],
        context: OperationExecutionContext,
    ) -> OperationResult:
        nonlocal calls
        del arguments, context
        calls += 1
        if calls == 1:
            return OperationResult.failed("unknown_provider_failure", "No retry contract exists.")
        return OperationResult.succeeded({"result": "must-not-run"})

    registration = _registration("fail-closed.v1", fail_unknown)
    nodes: tuple[ProgramNode, ...] = (
        ActionNode(
            node_id="fail-closed",
            operation_id="fail-closed.v1",
            retry=RetryPolicy(max_attempts=3, retry_on=("known_transient",)),
        ),
        StopNode(
            node_id="stop",
            depends_on=("fail-closed",),
            outcome=StopOutcome.SUCCEEDED,
        ),
    )

    result = execute_program(
        _program(nodes, (registration.reference,)),
        OperationRegistry((registration,)),
    )

    evidence = _evidence("fail-closed", result)
    assert result.status is ProgramExecutionStatus.FAILED
    assert evidence.error_code == "unknown_provider_failure"
    assert len(evidence.attempts) == 1
    assert calls == 1


def test_handler_receives_and_cannot_exceed_bounded_recursion_context() -> None:
    def recursive(arguments: Mapping[str, JsonValue], context: OperationExecutionContext) -> OperationResult:
        del arguments
        assert context.recursion.max_depth == 2
        assert context.recursion.max_calls == 1
        context.recursion.claim(depth=2)
        return OperationResult.succeeded({"result": "bounded"})

    registration = _registration("recursive.v1", recursive)
    nodes: tuple[ProgramNode, ...] = (
        ActionNode(
            node_id="recursive",
            operation_id="recursive.v1",
            recursion=RecursionPolicy(max_depth=2, max_calls=1),
        ),
        StopNode(
            node_id="stop",
            depends_on=("recursive",),
            outcome=StopOutcome.SUCCEEDED,
            result=ProgramOutputRef(node_id="recursive"),
        ),
    )

    result = execute_program(
        _program(
            nodes,
            (registration.reference,),
            limits=ProgramLimits(
                max_total_attempts=4,
                max_parallelism=1,
                max_recursion_depth=2,
                max_recursive_calls=1,
            ),
        ),
        OperationRegistry((registration,)),
    )

    attempt = _evidence("recursive", result).attempts[0]
    assert result.status is ProgramExecutionStatus.SUCCEEDED
    assert result.recursive_calls == 1
    assert attempt.recursive_calls == 1
    assert attempt.maximum_recursion_depth == 2


def test_recursion_claims_fail_at_the_declared_node_call_limit() -> None:
    def recursive(arguments: Mapping[str, JsonValue], context: OperationExecutionContext) -> OperationResult:
        del arguments
        context.recursion.claim(depth=1)
        context.recursion.claim(depth=1)
        return OperationResult.succeeded({"result": "unreachable"})

    registration = _registration("recursive.v1", recursive)
    nodes: tuple[ProgramNode, ...] = (
        ActionNode(
            node_id="recursive",
            operation_id="recursive.v1",
            recursion=RecursionPolicy(max_depth=1, max_calls=1),
        ),
        StopNode(node_id="stop", depends_on=("recursive",), outcome=StopOutcome.SUCCEEDED),
    )

    result = execute_program(
        _program(
            nodes,
            (registration.reference,),
            limits=ProgramLimits(
                max_total_attempts=2,
                max_parallelism=1,
                max_recursion_depth=1,
                max_recursive_calls=2,
            ),
        ),
        OperationRegistry((registration,)),
    )

    assert result.status is ProgramExecutionStatus.FAILED
    assert result.error_code == "node_recursive_call_budget_exhausted"
    assert result.recursive_calls == 1
    assert _evidence("recursive", result).attempts[0].recursive_calls == 1


def test_global_attempt_budget_fails_closed_during_fanout() -> None:
    def source(arguments: Mapping[str, JsonValue], context: OperationExecutionContext) -> OperationResult:
        del arguments, context
        return OperationResult.succeeded({"items": [1, 2, 3]})

    def identity(arguments: Mapping[str, JsonValue], context: OperationExecutionContext) -> OperationResult:
        del context
        return OperationResult.succeeded({"result": arguments["item"]})

    registrations = (
        _registration("source.v1", source),
        _registration("identity.v1", identity),
    )
    nodes: tuple[ProgramNode, ...] = (
        ActionNode(node_id="source", operation_id="source.v1"),
        FanoutNode(
            node_id="fanout",
            depends_on=("source",),
            operation_id="identity.v1",
            items=ProgramOutputRef(node_id="source", output_port="items"),
            item_argument="item",
            max_parallelism=1,
        ),
        StopNode(node_id="stop", depends_on=("fanout",), outcome=StopOutcome.SUCCEEDED),
    )

    result = execute_program(
        _program(
            nodes,
            tuple(registration.reference for registration in registrations),
            limits=ProgramLimits(max_total_attempts=3, max_parallelism=1),
        ),
        OperationRegistry(registrations),
    )

    assert result.status is ProgramExecutionStatus.FAILED
    assert result.error_code == "global_attempt_budget_exhausted"
    assert result.total_attempts == 3
    assert _evidence("fanout", result).status is NodeExecutionStatus.FAILED


def test_missing_handler_fails_closed_before_any_operation_attempt() -> None:
    operation_ref = _ref("missing.v1")
    nodes: tuple[ProgramNode, ...] = (
        ActionNode(node_id="missing", operation_id="missing.v1"),
        StopNode(node_id="stop", depends_on=("missing",), outcome=StopOutcome.SUCCEEDED),
    )

    result = execute_program(
        _program(nodes, (operation_ref,)),
        OperationRegistry(()),
    )

    assert result.status is ProgramExecutionStatus.FAILED
    assert result.error_code == "missing_operation_handler"
    assert result.total_attempts == 0


def test_invalid_handler_result_becomes_typed_failure_evidence() -> None:
    def invalid_handler(arguments: Mapping[str, JsonValue], context: OperationExecutionContext) -> object:
        del arguments, context
        return {"not": "an operation result"}

    registration = _registration(
        "invalid.v1",
        cast(OperationHandler, invalid_handler),
    )
    nodes: tuple[ProgramNode, ...] = (
        ActionNode(node_id="invalid", operation_id="invalid.v1"),
        StopNode(node_id="stop", depends_on=("invalid",), outcome=StopOutcome.SUCCEEDED),
    )

    result = execute_program(
        _program(nodes, (registration.reference,)),
        OperationRegistry((registration,)),
    )

    assert result.status is ProgramExecutionStatus.FAILED
    assert result.error_code == "invalid_handler_result"
    assert _evidence("invalid", result).attempts[0].error_code == "invalid_handler_result"


def test_missing_declared_output_port_fails_closed_without_calling_consumer() -> None:
    consumer_calls: list[str] = []

    def source(arguments: Mapping[str, JsonValue], context: OperationExecutionContext) -> OperationResult:
        del arguments, context
        return OperationResult.succeeded({"result": 1})

    def consumer(arguments: Mapping[str, JsonValue], context: OperationExecutionContext) -> OperationResult:
        del arguments, context
        consumer_calls.append("called")
        return OperationResult.succeeded({"result": 2})

    registrations = (
        _registration("source.v1", source),
        _registration("consumer.v1", consumer),
    )
    nodes: tuple[ProgramNode, ...] = (
        ActionNode(node_id="source", operation_id="source.v1"),
        ActionNode(
            node_id="consumer",
            depends_on=("source",),
            operation_id="consumer.v1",
            arguments=(
                ProgramArgument(
                    name="input",
                    value=OutputValue(ref=ProgramOutputRef(node_id="source", output_port="absent")),
                ),
            ),
        ),
        StopNode(node_id="stop", depends_on=("consumer",), outcome=StopOutcome.SUCCEEDED),
    )

    result = execute_program(
        _program(nodes, tuple(registration.reference for registration in registrations)),
        OperationRegistry(registrations),
    )

    assert result.status is ProgramExecutionStatus.FAILED
    assert result.error_code == "missing_output_port"
    assert consumer_calls == []


def test_failed_active_node_dominates_disconnected_success_stop() -> None:
    def fail(arguments: Mapping[str, JsonValue], context: OperationExecutionContext) -> OperationResult:
        del arguments, context
        return OperationResult.failed("provider_failed", "The provider rejected the operation.")

    registration = _registration("fail.v1", fail)
    nodes: tuple[ProgramNode, ...] = (
        ActionNode(node_id="failed-action", operation_id="fail.v1"),
        StopNode(
            node_id="failed-stop",
            depends_on=("failed-action",),
            outcome=StopOutcome.FAILED,
            message="The action failed.",
        ),
        StopNode(node_id="success-stop", outcome=StopOutcome.SUCCEEDED),
    )

    result = execute_program(
        _program(nodes, (registration.reference,)),
        OperationRegistry((registration,)),
    )

    assert result.status is ProgramExecutionStatus.FAILED
    assert result.stop_node_id is None
    assert result.error_code == "provider_failed"
    assert result.error_message == "The provider rejected the operation."
    assert _evidence("success-stop", result).status is NodeExecutionStatus.SUCCEEDED


def test_failed_active_node_dominates_disconnected_stopped_terminal() -> None:
    def fail(arguments: Mapping[str, JsonValue], context: OperationExecutionContext) -> OperationResult:
        del arguments, context
        return OperationResult.failed("provider_failed", "The provider rejected the operation.")

    registration = _registration("fail.v1", fail)
    nodes: tuple[ProgramNode, ...] = (
        ActionNode(node_id="failed-action", operation_id="fail.v1"),
        StopNode(node_id="failed-stop", depends_on=("failed-action",), outcome=StopOutcome.FAILED),
        StopNode(node_id="stopped-terminal", outcome=StopOutcome.STOPPED, message="Stopped independently."),
    )

    result = execute_program(
        _program(nodes, (registration.reference,)),
        OperationRegistry((registration,)),
    )

    assert result.status is ProgramExecutionStatus.FAILED
    assert result.stop_node_id is None
    assert result.error_code == "provider_failed"
    assert _evidence("stopped-terminal", result).status is NodeExecutionStatus.SUCCEEDED


def test_failed_stop_remains_a_typed_terminal_failure_without_an_earlier_failure() -> None:
    nodes: tuple[ProgramNode, ...] = (
        StopNode(node_id="failed-stop", outcome=StopOutcome.FAILED, message="Declared terminal failure."),
    )

    result = execute_program(
        _program(nodes, ()),
        OperationRegistry(()),
    )

    assert result.status is ProgramExecutionStatus.FAILED
    assert result.stop_node_id == "failed-stop"
    assert result.error_code == "stop_failed"
    assert result.error_message == "Declared terminal failure."


def test_program_execution_result_rejects_success_with_failed_node_evidence() -> None:
    with pytest.raises(ValidationError, match="cannot contain failed node evidence"):
        ProgramExecutionResult(
            program_ref=ExecutionProgramRef(program_id="px-runtime-test", version="1.0.0"),
            status=ProgramExecutionStatus.SUCCEEDED,
            stop_node_id="success-stop",
            total_attempts=1,
            maximum_parallelism_observed=1,
            recursive_calls=0,
            maximum_recursion_depth=0,
            node_evidence=(
                NodeExecutionEvidence(
                    node_id="failed-action",
                    kind=ProgramNodeKind.ACTION,
                    status=NodeExecutionStatus.FAILED,
                    dependency_node_ids=(),
                    error_code="provider_failed",
                    error_message="The provider rejected the operation.",
                ),
                NodeExecutionEvidence(
                    node_id="success-stop",
                    kind=ProgramNodeKind.STOP,
                    status=NodeExecutionStatus.SUCCEEDED,
                    dependency_node_ids=(),
                ),
            ),
        )


@pytest.mark.parametrize("status", [ProgramExecutionStatus.SUCCEEDED, ProgramExecutionStatus.STOPPED])
def test_program_execution_result_requires_reached_stop_for_nonfailure(
    status: ProgramExecutionStatus,
) -> None:
    with pytest.raises(ValidationError, match="require a reached stop node"):
        ProgramExecutionResult(
            program_ref=ExecutionProgramRef(program_id="px-runtime-test", version="1.0.0"),
            status=status,
            total_attempts=0,
            maximum_parallelism_observed=0,
            recursive_calls=0,
            maximum_recursion_depth=0,
            node_evidence=(),
        )


def test_program_execution_result_rejects_error_fields_on_success() -> None:
    with pytest.raises(ValidationError, match="cannot contain error fields"):
        ProgramExecutionResult(
            program_ref=ExecutionProgramRef(program_id="px-runtime-test", version="1.0.0"),
            status=ProgramExecutionStatus.SUCCEEDED,
            stop_node_id="success-stop",
            error_code="forged_error",
            total_attempts=0,
            maximum_parallelism_observed=0,
            recursive_calls=0,
            maximum_recursion_depth=0,
            node_evidence=(
                NodeExecutionEvidence(
                    node_id="success-stop",
                    kind=ProgramNodeKind.STOP,
                    status=NodeExecutionStatus.SUCCEEDED,
                    dependency_node_ids=(),
                ),
            ),
        )


def test_program_execution_result_requires_error_code_for_failure() -> None:
    with pytest.raises(ValidationError, match="failed program results require an error code"):
        ProgramExecutionResult(
            program_ref=ExecutionProgramRef(program_id="px-runtime-test", version="1.0.0"),
            status=ProgramExecutionStatus.FAILED,
            total_attempts=0,
            maximum_parallelism_observed=0,
            recursive_calls=0,
            maximum_recursion_depth=0,
            node_evidence=(),
        )


def test_program_execution_result_rejects_success_data_without_a_failed_stop() -> None:
    with pytest.raises(ValidationError, match="cannot contain terminal success data"):
        ProgramExecutionResult(
            program_ref=ExecutionProgramRef(program_id="px-runtime-test", version="1.0.0"),
            status=ProgramExecutionStatus.FAILED,
            result="forged-success",
            error_code="provider_failed",
            total_attempts=1,
            maximum_parallelism_observed=1,
            recursive_calls=0,
            maximum_recursion_depth=0,
            node_evidence=(
                NodeExecutionEvidence(
                    node_id="failed-action",
                    kind=ProgramNodeKind.ACTION,
                    status=NodeExecutionStatus.FAILED,
                    dependency_node_ids=(),
                    error_code="provider_failed",
                ),
            ),
        )
