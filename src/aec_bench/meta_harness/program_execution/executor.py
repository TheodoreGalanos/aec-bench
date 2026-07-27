# ABOUTME: Executes compiled program DAGs against an explicitly injected trusted registry.
# ABOUTME: Enforces activation, dataflow, retry, fanout, branch, stop, and evidence invariants.


from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Literal, cast

from pydantic import JsonValue, ValidationError

from aec_bench.contracts.execution_program import (
    ActionNode,
    BranchNode,
    BranchOperator,
    CompiledExecutionProgram,
    FanoutNode,
    JoinNode,
    JoinStrategy,
    LiteralValue,
    OutputValue,
    ProgramArgument,
    ProgramNode,
    ProgramOutputRef,
    RecursionPolicy,
    RetryPolicy,
    StopNode,
    StopOutcome,
    VerifyNode,
)
from aec_bench.contracts.harness_kernel import (
    canonical_content_sha256,
)

from .budget import (
    BoundedRecursionContext,
    OperationExecutionContext,
    _NodeRecursionState,
    _RuntimeBudget,
    _RuntimeFault,
)
from .contracts import (
    InputBindingLineage,
    NodeExecutionEvidence,
    NodeExecutionStatus,
    OperationAttemptEvidence,
    OperationExecutionStatus,
    OperationHandlerFailure,
    OperationLineage,
    OperationResult,
    ProgramExecutionResult,
    ProgramExecutionStatus,
)
from .registry import OperationRegistration, OperationRegistry


@dataclass(frozen=True)
class _InvocationResult:
    succeeded: bool
    outputs: dict[str, JsonValue]
    attempts: tuple[OperationAttemptEvidence, ...]
    error_code: str | None
    error_message: str | None
    fatal: bool


@dataclass(frozen=True)
class _ExecutedNode:
    evidence: NodeExecutionEvidence
    fatal: bool = False


class _ProgramExecutor:
    def __init__(
        self,
        program: CompiledExecutionProgram,
        registry: OperationRegistry,
        sleeper: Callable[[float], None],
    ) -> None:
        self.program = program
        self.registry = registry
        self.sleeper = sleeper
        self.budget = _RuntimeBudget(program)
        self.nodes_by_id = {node.node_id: node for node in program.nodes}
        self.operation_refs = {reference.operation_id: reference for reference in program.operation_refs}
        self.outputs: dict[str, dict[str, JsonValue]] = {}
        self.statuses: dict[str, NodeExecutionStatus] = {}
        self.branch_choices: dict[str, str] = {}
        self.branch_controls = _branch_controls(program.nodes)
        self.recursion_states = {
            node.node_id: _recursion_state(node.recursion)
            for node in program.nodes
            if isinstance(node, ActionNode | FanoutNode)
        }

    def execute(self) -> ProgramExecutionResult:
        evidence: list[NodeExecutionEvidence] = []
        terminal: tuple[StopNode, JsonValue] | None = None
        fatal_fault: tuple[str, str] | None = None
        first_failure: tuple[str, str] | None = None
        terminated = False

        for node_id in self.program.topological_order:
            node = self.nodes_by_id[node_id]
            if terminated:
                executed = _ExecutedNode(_skipped_evidence(node, "program_already_terminated"))
            else:
                activation_error = self._activation_error(node)
                if activation_error is not None:
                    executed = _ExecutedNode(_skipped_evidence(node, activation_error))
                else:
                    executed = self._execute_node(node)

            node_evidence = executed.evidence
            evidence.append(node_evidence)
            self.statuses[node.node_id] = node_evidence.status
            if node_evidence.status is NodeExecutionStatus.SUCCEEDED:
                self.outputs[node.node_id] = node_evidence.outputs
            elif node_evidence.status is NodeExecutionStatus.FAILED and first_failure is None:
                first_failure = (
                    node_evidence.error_code or "node_execution_failed",
                    node_evidence.error_message or f"node {node.node_id!r} failed",
                )

            if isinstance(node, BranchNode) and node_evidence.status is NodeExecutionStatus.SUCCEEDED:
                assert node_evidence.selected_successor_node_id is not None
                self.branch_choices[node.node_id] = node_evidence.selected_successor_node_id
            if isinstance(node, StopNode) and node_evidence.status is NodeExecutionStatus.SUCCEEDED:
                terminal = (node, node_evidence.outputs.get("result"))
                terminated = True
            if executed.fatal:
                fatal_fault = (
                    node_evidence.error_code or "runtime_fault",
                    node_evidence.error_message or f"fatal runtime fault at node {node.node_id!r}",
                )
                terminated = True

        return self._result(
            evidence=tuple(evidence),
            terminal=terminal,
            fatal_fault=fatal_fault,
            first_failure=first_failure,
        )

    def _activation_error(self, node: ProgramNode) -> str | None:
        controls = self.branch_controls.get(node.node_id, ())
        if any(branch_id not in self.branch_choices for branch_id in controls):
            return "branch_not_active"
        if any(self.branch_choices[branch_id] != node.node_id for branch_id in controls):
            return "branch_not_selected"
        if isinstance(node, JoinNode):
            return None
        if any(self.statuses.get(dependency) is not NodeExecutionStatus.SUCCEEDED for dependency in node.depends_on):
            return "inactive_dependency"
        return None

    def _execute_node(self, node: ProgramNode) -> _ExecutedNode:
        try:
            if isinstance(node, ActionNode):
                return self._execute_action(node)
            if isinstance(node, FanoutNode):
                return self._execute_fanout(node)
            if isinstance(node, JoinNode):
                return self._execute_join(node)
            if isinstance(node, BranchNode):
                return self._execute_branch(node)
            if isinstance(node, VerifyNode):
                return self._execute_verify(node)
            return self._execute_stop(node)
        except _RuntimeFault as error:
            return _ExecutedNode(
                _failed_evidence(node, error.code, str(error)),
                fatal=True,
            )

    def _execute_action(self, node: ActionNode) -> _ExecutedNode:
        arguments, bindings = self._bind_arguments(node.arguments)
        registration = self._resolve_registration(node.operation_id)
        invocation = self._invoke(
            node=node,
            registration=registration,
            arguments=arguments,
            retry=node.retry,
            fanout_index=None,
        )
        return _executed_operation_node(node, registration, bindings, invocation)

    def _execute_verify(self, node: VerifyNode) -> _ExecutedNode:
        arguments, bindings = self._bind_arguments(node.arguments)
        if "subject" in arguments:
            raise _RuntimeFault(
                "reserved_argument_collision",
                f"verify node {node.node_id!r} declares reserved argument 'subject'",
            )
        subject = self._resolve_output(node.subject)
        arguments["subject"] = subject
        bindings = (
            *bindings,
            _input_binding("subject", "verify_subject", node.subject, subject),
        )
        registration = self._resolve_registration(node.operation_id)
        invocation = self._invoke(
            node=node,
            registration=registration,
            arguments=arguments,
            retry=node.retry,
            fanout_index=None,
        )
        return _executed_operation_node(node, registration, bindings, invocation)

    def _execute_fanout(self, node: FanoutNode) -> _ExecutedNode:
        base_arguments, base_bindings = self._bind_arguments(node.arguments)
        if node.item_argument in base_arguments:
            raise _RuntimeFault(
                "reserved_argument_collision",
                f"fanout node {node.node_id!r} item argument collides with a declared argument",
            )
        items = self._resolve_output(node.items)
        if not isinstance(items, list):
            raise _RuntimeFault(
                "fanout_items_not_array",
                f"fanout node {node.node_id!r} items port must contain a JSON array",
            )
        registration = self._resolve_registration(node.operation_id)
        max_workers = min(
            node.max_parallelism,
            registration.max_parallelism,
            self.program.limits.max_parallelism,
        )
        item_bindings = tuple(
            _input_binding(
                node.item_argument,
                "fanout_item",
                node.items,
                item,
                fanout_index=index,
            )
            for index, item in enumerate(items)
        )
        all_bindings = (
            *base_bindings,
            _input_binding("items", "fanout_items", node.items, items),
            *item_bindings,
        )

        def invoke_item(index: int, item: JsonValue) -> _InvocationResult:
            arguments = _copy_json_object(base_arguments)
            arguments[node.item_argument] = _copy_json(item)
            return self._invoke(
                node=node,
                registration=registration,
                arguments=arguments,
                retry=node.retry,
                fanout_index=index,
            )

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(invoke_item, index, item) for index, item in enumerate(items)]
            invocations = tuple(future.result() for future in futures)

        attempts = tuple(
            sorted(
                (attempt for invocation in invocations for attempt in invocation.attempts),
                key=lambda attempt: (
                    -1 if attempt.fanout_index is None else attempt.fanout_index,
                    attempt.attempt_index,
                ),
            )
        )
        failure = next((invocation for invocation in invocations if not invocation.succeeded), None)
        if failure is not None:
            return _ExecutedNode(
                NodeExecutionEvidence(
                    node_id=node.node_id,
                    kind=node.kind,
                    status=NodeExecutionStatus.FAILED,
                    dependency_node_ids=node.depends_on,
                    input_bindings=all_bindings,
                    operation_lineage=_operation_lineage(registration),
                    attempts=attempts,
                    error_code=failure.error_code or "fanout_item_failed",
                    error_message=failure.error_message,
                ),
                fatal=failure.fatal,
            )
        outputs = _aggregate_fanout_outputs(invocations)
        return _ExecutedNode(
            NodeExecutionEvidence(
                node_id=node.node_id,
                kind=node.kind,
                status=NodeExecutionStatus.SUCCEEDED,
                dependency_node_ids=node.depends_on,
                input_bindings=all_bindings,
                operation_lineage=_operation_lineage(registration),
                attempts=attempts,
                outputs=outputs,
            )
        )

    def _execute_join(self, node: JoinNode) -> _ExecutedNode:
        available: list[tuple[ProgramOutputRef, JsonValue]] = []
        for source in node.sources:
            if self.statuses.get(source.node_id) is NodeExecutionStatus.SUCCEEDED:
                available.append((source, self._resolve_output(source)))

        if node.strategy is JoinStrategy.ALL and len(available) != len(node.sources):
            return _ExecutedNode(
                _failed_evidence(
                    node,
                    "join_sources_not_ready",
                    f"join node {node.node_id!r} requires all sources to succeed",
                )
            )
        if not available:
            return _ExecutedNode(
                _failed_evidence(
                    node,
                    "join_sources_not_ready",
                    f"join node {node.node_id!r} has no successful sources",
                )
            )

        selected = available[:1] if node.strategy is JoinStrategy.FIRST_SUCCESS else available
        values = [_copy_json(value) for _, value in selected]
        result: JsonValue = values[0] if node.strategy is JoinStrategy.FIRST_SUCCESS else values
        bindings = tuple(
            _input_binding(f"source[{index}]", "join_source", source, value)
            for index, (source, value) in enumerate(selected)
        )
        return _ExecutedNode(
            NodeExecutionEvidence(
                node_id=node.node_id,
                kind=node.kind,
                status=NodeExecutionStatus.SUCCEEDED,
                dependency_node_ids=node.depends_on,
                input_bindings=bindings,
                outputs={
                    "result": result,
                    "source_node_ids": [source.node_id for source, _ in selected],
                },
            )
        )

    def _execute_branch(self, node: BranchNode) -> _ExecutedNode:
        value = self._resolve_output(node.condition.value)
        selected = (
            node.true_node_id
            if _evaluate_branch(value, node.condition.operator, node.condition.expected)
            else node.false_node_id
        )
        binding = _input_binding("condition", "branch_condition", node.condition.value, value)
        return _ExecutedNode(
            NodeExecutionEvidence(
                node_id=node.node_id,
                kind=node.kind,
                status=NodeExecutionStatus.SUCCEEDED,
                dependency_node_ids=node.depends_on,
                input_bindings=(binding,),
                outputs={"selected_node_id": selected},
                selected_successor_node_id=selected,
            )
        )

    def _execute_stop(self, node: StopNode) -> _ExecutedNode:
        if node.result is None:
            result: JsonValue = None
            bindings: tuple[InputBindingLineage, ...] = ()
        else:
            result = self._resolve_output(node.result)
            bindings = (_input_binding("result", "stop_result", node.result, result),)
        return _ExecutedNode(
            NodeExecutionEvidence(
                node_id=node.node_id,
                kind=node.kind,
                status=NodeExecutionStatus.SUCCEEDED,
                dependency_node_ids=node.depends_on,
                input_bindings=bindings,
                outputs={"result": result},
            )
        )

    def _bind_arguments(
        self,
        arguments: tuple[ProgramArgument, ...],
    ) -> tuple[dict[str, JsonValue], tuple[InputBindingLineage, ...]]:
        values: dict[str, JsonValue] = {}
        bindings: list[InputBindingLineage] = []
        for argument in arguments:
            if isinstance(argument.value, LiteralValue):
                value = _copy_json(argument.value.value)
                binding = InputBindingLineage(
                    argument_name=argument.name,
                    source_kind="literal",
                    value_sha256=canonical_content_sha256(value),
                )
            elif isinstance(argument.value, OutputValue):
                value = self._resolve_output(argument.value.ref)
                binding = _input_binding(argument.name, "output", argument.value.ref, value)
            else:
                raise _RuntimeFault("unsupported_program_value", "program argument has an unsupported value kind")
            values[argument.name] = value
            bindings.append(binding)
        return values, tuple(bindings)

    def _resolve_output(self, reference: ProgramOutputRef) -> JsonValue:
        node_outputs = self.outputs.get(reference.node_id)
        if node_outputs is None or reference.output_port not in node_outputs:
            raise _RuntimeFault(
                "missing_output_port",
                f"node {reference.node_id!r} did not produce declared port {reference.output_port!r}",
            )
        return _copy_json(node_outputs[reference.output_port])

    def _resolve_registration(self, operation_id: str) -> OperationRegistration:
        reference = self.operation_refs[operation_id]
        registration = self.registry.registration(operation_id)
        if registration is None:
            raise _RuntimeFault(
                "missing_operation_handler",
                f"no trusted handler was registered for operation {operation_id!r}",
            )
        if self.registry.resolve(reference) is None:
            raise _RuntimeFault(
                "operation_reference_mismatch",
                f"trusted handler identity does not match compiled operation {operation_id!r}",
            )
        return registration

    def _invoke(
        self,
        *,
        node: ActionNode | FanoutNode | VerifyNode,
        registration: OperationRegistration,
        arguments: dict[str, JsonValue],
        retry: RetryPolicy | None,
        fanout_index: int | None,
    ) -> _InvocationResult:
        max_attempts = 1 if retry is None else retry.max_attempts
        attempts: list[OperationAttemptEvidence] = []
        recursion_state = self.recursion_states.get(node.node_id, _NodeRecursionState(0, 0))

        for attempt_index in range(1, max_attempts + 1):
            try:
                self.budget.claim_attempt()
            except _RuntimeFault as error:
                return _InvocationResult(False, {}, tuple(attempts), error.code, str(error), True)

            recursion = BoundedRecursionContext(self.budget, recursion_state)
            context = OperationExecutionContext(
                program_sha256=self.program.content_sha256,
                node_id=node.node_id,
                operation_ref=registration.reference,
                binding_ids=registration.binding_ids,
                attempt_index=attempt_index,
                fanout_index=fanout_index,
                recursion=recursion,
            )
            result, fatal = self._call_handler(
                registration=registration,
                arguments=arguments,
                context=context,
            )

            attempt = OperationAttemptEvidence(
                node_id=node.node_id,
                operation_id=registration.reference.operation_id,
                operation_sha256=registration.reference.content_sha256,
                attempt_index=attempt_index,
                fanout_index=fanout_index,
                arguments_sha256=canonical_content_sha256(arguments),
                status=result.status,
                outputs_sha256=(
                    canonical_content_sha256(result.outputs)
                    if result.status is OperationExecutionStatus.SUCCEEDED
                    else None
                ),
                error_code=result.error_code,
                error_message=result.error_message,
                recursive_calls=recursion.calls_used,
                maximum_recursion_depth=recursion.maximum_depth_used,
            )
            attempts.append(attempt)
            if result.status is OperationExecutionStatus.SUCCEEDED:
                return _InvocationResult(True, _copy_json_object(result.outputs), tuple(attempts), None, None, False)
            if fatal or not _should_retry(result.error_code, retry, attempt_index):
                return _InvocationResult(
                    False,
                    {},
                    tuple(attempts),
                    result.error_code,
                    result.error_message,
                    fatal,
                )
            assert retry is not None
            if retry.backoff_seconds:
                self.sleeper(retry.backoff_seconds)

        raise AssertionError("bounded invocation loop must return")

    def _call_handler(
        self,
        *,
        registration: OperationRegistration,
        arguments: dict[str, JsonValue],
        context: OperationExecutionContext,
    ) -> tuple[OperationResult, bool]:
        try:
            with self.budget.operation_slot():
                raw_result: object = registration.handler(_copy_json_object(arguments), context)
        except _RuntimeFault as error:
            return OperationResult.failed(error.code, str(error)), True
        except OperationHandlerFailure as error:
            return OperationResult.failed(error.code, str(error)), False
        except Exception as error:  # trusted boundary: convert implementation exceptions to typed evidence
            message = str(error).strip() or type(error).__name__
            return OperationResult.failed("handler_exception", message), False
        try:
            return OperationResult.model_validate(raw_result), False
        except ValidationError:
            return (
                OperationResult.failed(
                    "invalid_handler_result",
                    "trusted operation handler did not return a valid OperationResult",
                ),
                True,
            )

    def _result(
        self,
        *,
        evidence: tuple[NodeExecutionEvidence, ...],
        terminal: tuple[StopNode, JsonValue] | None,
        fatal_fault: tuple[str, str] | None,
        first_failure: tuple[str, str] | None,
    ) -> ProgramExecutionResult:
        failure = fatal_fault or first_failure
        if failure is not None:
            return ProgramExecutionResult(
                program_sha256=self.program.content_sha256,
                status=ProgramExecutionStatus.FAILED,
                error_code=failure[0],
                error_message=failure[1],
                total_attempts=self.budget.total_attempts,
                maximum_parallelism_observed=self.budget.maximum_parallelism_observed,
                recursive_calls=self.budget.recursive_calls,
                maximum_recursion_depth=self.budget.maximum_recursion_depth_observed,
                node_evidence=evidence,
            )
        if terminal is not None:
            stop, result = terminal
            status = {
                StopOutcome.SUCCEEDED: ProgramExecutionStatus.SUCCEEDED,
                StopOutcome.FAILED: ProgramExecutionStatus.FAILED,
                StopOutcome.STOPPED: ProgramExecutionStatus.STOPPED,
            }[stop.outcome]
            return ProgramExecutionResult(
                program_sha256=self.program.content_sha256,
                status=status,
                stop_node_id=stop.node_id,
                result=result,
                message=stop.message,
                error_code="stop_failed" if stop.outcome is StopOutcome.FAILED else None,
                error_message=stop.message if stop.outcome is StopOutcome.FAILED else None,
                total_attempts=self.budget.total_attempts,
                maximum_parallelism_observed=self.budget.maximum_parallelism_observed,
                recursive_calls=self.budget.recursive_calls,
                maximum_recursion_depth=self.budget.maximum_recursion_depth_observed,
                node_evidence=evidence,
            )
        failure = ("no_active_stop", "program completed without an active stop node")
        return ProgramExecutionResult(
            program_sha256=self.program.content_sha256,
            status=ProgramExecutionStatus.FAILED,
            error_code=failure[0],
            error_message=failure[1],
            total_attempts=self.budget.total_attempts,
            maximum_parallelism_observed=self.budget.maximum_parallelism_observed,
            recursive_calls=self.budget.recursive_calls,
            maximum_recursion_depth=self.budget.maximum_recursion_depth_observed,
            node_evidence=evidence,
        )


def execute_program(
    program: CompiledExecutionProgram,
    registry: OperationRegistry,
    *,
    sleeper: Callable[[float], None] = time.sleep,
) -> ProgramExecutionResult:
    """Execute one compiled px program against only the explicitly injected trusted registry."""

    normalized = CompiledExecutionProgram.model_validate(program.model_dump(mode="json"))
    return _ProgramExecutor(normalized, registry, sleeper).execute()


def _executed_operation_node(
    node: ActionNode | VerifyNode,
    registration: OperationRegistration,
    bindings: tuple[InputBindingLineage, ...],
    invocation: _InvocationResult,
) -> _ExecutedNode:
    status = NodeExecutionStatus.SUCCEEDED if invocation.succeeded else NodeExecutionStatus.FAILED
    return _ExecutedNode(
        NodeExecutionEvidence(
            node_id=node.node_id,
            kind=node.kind,
            status=status,
            dependency_node_ids=node.depends_on,
            input_bindings=bindings,
            operation_lineage=_operation_lineage(registration),
            attempts=invocation.attempts,
            outputs=invocation.outputs,
            error_code=invocation.error_code,
            error_message=invocation.error_message,
        ),
        fatal=invocation.fatal,
    )


def _aggregate_fanout_outputs(invocations: tuple[_InvocationResult, ...]) -> dict[str, JsonValue]:
    if not invocations:
        return {"result": []}
    output_ports = tuple(sorted(invocations[0].outputs))
    if any(tuple(sorted(invocation.outputs)) != output_ports for invocation in invocations[1:]):
        raise _RuntimeFault(
            "inconsistent_fanout_output_ports",
            "fanout handler invocations produced inconsistent output ports",
        )
    return {
        output_port: [_copy_json(invocation.outputs[output_port]) for invocation in invocations]
        for output_port in output_ports
    }


def _operation_lineage(registration: OperationRegistration) -> OperationLineage:
    return OperationLineage(
        operation_id=registration.reference.operation_id,
        operation_sha256=registration.reference.content_sha256,
        binding_ids=registration.binding_ids,
    )


def _input_binding(
    argument_name: str,
    source_kind: Literal[
        "output",
        "fanout_item",
        "fanout_items",
        "verify_subject",
        "join_source",
        "branch_condition",
        "stop_result",
    ],
    reference: ProgramOutputRef,
    value: JsonValue,
    *,
    fanout_index: int | None = None,
) -> InputBindingLineage:
    return InputBindingLineage(
        argument_name=argument_name,
        source_kind=source_kind,
        source_node_id=reference.node_id,
        source_output_port=reference.output_port,
        fanout_index=fanout_index,
        value_sha256=canonical_content_sha256(value),
    )


def _failed_evidence(
    node: ProgramNode,
    error_code: str,
    error_message: str,
) -> NodeExecutionEvidence:
    return NodeExecutionEvidence(
        node_id=node.node_id,
        kind=node.kind,
        status=NodeExecutionStatus.FAILED,
        dependency_node_ids=node.depends_on,
        error_code=error_code,
        error_message=error_message,
    )


def _skipped_evidence(node: ProgramNode, error_code: str) -> NodeExecutionEvidence:
    return NodeExecutionEvidence(
        node_id=node.node_id,
        kind=node.kind,
        status=NodeExecutionStatus.SKIPPED,
        dependency_node_ids=node.depends_on,
        error_code=error_code,
    )


def _branch_controls(nodes: tuple[ProgramNode, ...]) -> dict[str, tuple[str, ...]]:
    controls: dict[str, list[str]] = {}
    for node in nodes:
        if isinstance(node, BranchNode):
            controls.setdefault(node.true_node_id, []).append(node.node_id)
            controls.setdefault(node.false_node_id, []).append(node.node_id)
    return {node_id: tuple(sorted(branch_ids)) for node_id, branch_ids in controls.items()}


def _recursion_state(policy: RecursionPolicy | None) -> _NodeRecursionState:
    if policy is None:
        return _NodeRecursionState(0, 0)
    return _NodeRecursionState(policy.max_depth, policy.max_calls)


def _should_retry(error_code: str | None, retry: RetryPolicy | None, attempt_index: int) -> bool:
    if retry is None or attempt_index >= retry.max_attempts:
        return False
    return error_code is not None and error_code in retry.retry_on


def _evaluate_branch(value: JsonValue, operator: BranchOperator, expected: JsonValue) -> bool:
    try:
        if operator is BranchOperator.EQUALS:
            return value == expected
        if operator is BranchOperator.NOT_EQUALS:
            return value != expected
        if operator is BranchOperator.GREATER_THAN:
            return value > expected  # type: ignore[operator]
        if operator is BranchOperator.GREATER_THAN_OR_EQUAL:
            return value >= expected  # type: ignore[operator]
        if operator is BranchOperator.LESS_THAN:
            return value < expected  # type: ignore[operator]
        if operator is BranchOperator.LESS_THAN_OR_EQUAL:
            return value <= expected  # type: ignore[operator]
        if operator is BranchOperator.CONTAINS:
            return expected in value  # type: ignore[operator]
        return value is not None
    except (TypeError, ValueError) as error:
        raise _RuntimeFault(
            "invalid_branch_operands",
            f"branch operator {operator.value!r} cannot compare the supplied values",
        ) from error


def _copy_json(value: JsonValue) -> JsonValue:
    return cast(JsonValue, json.loads(json.dumps(value, sort_keys=True, separators=(",", ":"))))


def _copy_json_object(value: Mapping[str, JsonValue]) -> dict[str, JsonValue]:
    copied = _copy_json(dict(value))
    assert isinstance(copied, dict)
    return copied
