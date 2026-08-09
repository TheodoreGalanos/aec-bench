# ABOUTME: Resolves fixed-kernel program operations and validates their closed argument ABIs.
# ABOUTME: Preserves migrated definitions, legacy compatibility, and retry-taxonomy attribution.

from aec_bench.contracts.execution_program import (
    ActionNode,
    FanoutNode,
    LiteralValue,
    OutputValue,
    ProgramArgument,
    VerifyNode,
)
from aec_bench.contracts.harness_instance import (
    ProgramOperationSpec,
    prohibited_retry_safe_error_codes,
)
from aec_bench.contracts.harness_kernel import KernelCapabilitySpec
from aec_bench.harness.kernel_catalogue import (
    KernelOperationArgumentPolicy,
    KernelOperationArgumentSource,
    KernelOperationArgumentSpec,
    KernelOperationDefinition,
    KernelRuntimeRegistry,
    ProgramOperationRuntime,
)

from .diagnostics import CompilationOwner, _fail
from .profile import ProgramCompilationProfile


def _resolve_program_operation_capability(
    *,
    registry: KernelRuntimeRegistry,
    capability_id: str,
    operation_id: str,
) -> tuple[KernelCapabilitySpec, ProgramOperationRuntime]:
    capability = registry.capability(capability_id)
    primitive = registry.resolve(capability.ref)
    if not isinstance(primitive.runtime, ProgramOperationRuntime):
        _fail(
            owner=CompilationOwner.KERNEL,
            code="program_operation_runtime_invalid",
            message=f"{operation_id} capability does not resolve to a trusted program operation runtime",
            subject_ids=(capability.capability_id,),
        )
    prohibited = prohibited_retry_safe_error_codes(primitive.runtime.retry_safe_error_codes)
    if prohibited:
        _fail(
            owner=CompilationOwner.KERNEL,
            code="program_operation_retry_taxonomy_unsafe",
            message=f"fixed-K {operation_id} operation declares prohibited retry-safe error codes",
            subject_ids=prohibited,
        )
    return capability, primitive.runtime


def _resolve_program_operation_abi(
    *,
    registry: KernelRuntimeRegistry,
    operation_id: str,
    capability_id: str,
    input_schema_ref: str,
    output_schema_ref: str,
) -> tuple[str, KernelCapabilitySpec, ProgramOperationRuntime, str, str]:
    """Resolve migrated operation metadata while retaining the exact legacy v1 fallback."""
    definition = registry.operation_definition(operation_id)
    if definition is None:
        if not registry.is_legacy_definition_free:
            _fail(
                owner=CompilationOwner.KERNEL,
                code="operation_definition_missing",
                message=("fixed-K operation lacks its phase-neutral definition: " + operation_id),
                subject_ids=(operation_id,),
            )
        capability, runtime = _resolve_program_operation_capability(
            registry=registry,
            capability_id=capability_id,
            operation_id=operation_id,
        )
        return (
            operation_id,
            capability,
            runtime,
            input_schema_ref,
            output_schema_ref,
        )
    capability, runtime = _resolve_program_operation_capability(
        registry=registry,
        capability_id=definition.capability.capability_id,
        operation_id=definition.operation_id,
    )
    if capability != definition.capability or runtime != definition.runtime:
        _fail(
            owner=CompilationOwner.KERNEL,
            code="operation_definition_mismatch",
            message=("kernel operation definition differs from its installed runtime primitive: " + operation_id),
            subject_ids=(operation_id,),
        )
    return (
        definition.operation_id,
        definition.capability,
        definition.runtime,
        definition.input_schema_ref,
        definition.output_schema_ref,
    )


def _validate_operation_arguments(
    node: ActionNode | FanoutNode | VerifyNode,
    *,
    operation: ProgramOperationSpec,
    profile: ProgramCompilationProfile,
    registry: KernelRuntimeRegistry,
) -> None:
    """Validate the closed argument ABI of fixed-K program operations."""
    definition = _operation_definition_for_compilation(
        registry=registry,
        operation=operation,
    )
    if definition is not None:
        _validate_definition_arguments(
            node,
            definition=definition,
            operation=operation,
            profile=profile,
        )
        return
    if not registry.is_legacy_definition_free:
        _fail(
            owner=CompilationOwner.KERNEL,
            code="operation_definition_missing",
            message=("fixed-K operation lacks its phase-neutral definition: " + operation.operation_id),
            subject_ids=(operation.operation_id,),
        )
    _validate_legacy_operation_arguments(
        node,
        operation=operation,
        profile=profile,
    )


def _validate_legacy_operation_arguments(
    node: ActionNode | FanoutNode | VerifyNode,
    *,
    operation: ProgramOperationSpec,
    profile: ProgramCompilationProfile,
) -> None:
    """Preserve the exact v1 ABI only for an explicit definition-free registry."""
    names = {argument.name for argument in node.arguments}
    if node.operation_id == "enumerate_tasks.v1":
        _validate_legacy_enumeration(node=node, names=names)
        return
    if node.operation_id in {
        "run_proposal_session.v1",
        "run_semantic_subtask.v1",
    }:
        _validate_legacy_argument_free_action(node=node, names=names)
        return
    if node.operation_id in {
        "check_subtask_contract.v1",
        "finalize_proposed_plan.v1",
    }:
        _validate_legacy_single_output_action(
            node=node,
            names=names,
            profile=profile,
        )
        return
    if node.operation_id == "run_stage.v1":
        _validate_legacy_run_stage(
            node=node,
            names=names,
            operation=operation,
        )
        return
    if node.operation_id == "finalize_task.v1":
        _validate_legacy_finalize_task(
            node=node,
            names=names,
            operation=operation,
        )
        return
    if node.operation_id == "run_batch.v1":
        _validate_legacy_run_batch(node=node, names=names)


def _validate_legacy_enumeration(
    *,
    node: ActionNode | FanoutNode | VerifyNode,
    names: set[str],
) -> None:
    if names or isinstance(node, FanoutNode):
        _fail(
            owner=CompilationOwner.PROGRAM,
            code="operation_argument_unsupported",
            message="enumerate_tasks.v1 accepts no arguments and cannot be a fanout target",
            subject_ids=(node.node_id, *tuple(sorted(names))),
        )


def _validate_legacy_argument_free_action(
    *,
    node: ActionNode | FanoutNode | VerifyNode,
    names: set[str],
) -> None:
    if names or not isinstance(node, ActionNode):
        _fail(
            owner=CompilationOwner.PROGRAM,
            code="operation_argument_unsupported",
            message=f"{node.operation_id} is an argument-free action whose exact context is supplied by the compiler",
            subject_ids=(node.node_id, *tuple(sorted(names))),
        )


def _validate_legacy_single_output_action(
    *,
    node: ActionNode | FanoutNode | VerifyNode,
    names: set[str],
    profile: ProgramCompilationProfile,
) -> None:
    if (
        node.operation_id == "finalize_proposed_plan.v1"
        and profile is ProgramCompilationProfile.MONOLITHIC_INCUMBENT
        and isinstance(node, ActionNode)
        and not node.arguments
        and not node.depends_on
    ):
        return
    argument_name = "subject" if node.operation_id == "check_subtask_contract.v1" else "findings"
    argument = next(
        (candidate for candidate in node.arguments if candidate.name == argument_name),
        None,
    )
    valid = (
        isinstance(node, ActionNode)
        and names == {argument_name}
        and argument is not None
        and isinstance(argument.value, OutputValue)
        and argument.value.ref.output_port == "result"
    )
    if not valid:
        _fail(
            owner=CompilationOwner.PROGRAM,
            code="operation_argument_unsupported",
            message=f"{node.operation_id} requires exactly one output-derived {argument_name} argument",
            subject_ids=(node.node_id, *tuple(sorted(names))),
        )


def _validate_legacy_run_stage(
    *,
    node: ActionNode | FanoutNode | VerifyNode,
    names: set[str],
    operation: ProgramOperationSpec,
) -> None:
    arguments = {argument.name: argument for argument in node.arguments}
    valid_names = names in (
        {"task_ref", "stage_id"},
        {"task_ref", "stage_id", "upstream_receipts"},
    )
    valid_shape = isinstance(node, ActionNode) and valid_names
    task_ref = _literal_string(arguments.get("task_ref"))
    stage_id = _literal_string(arguments.get("stage_id"))
    upstream = arguments.get("upstream_receipts")
    valid_upstream = upstream is None or (
        isinstance(upstream.value, OutputValue) and upstream.value.ref.output_port in {"stage_receipt", "result"}
    )
    if (
        not valid_shape
        or task_ref is None
        or stage_id is None
        or not valid_upstream
        or task_ref not in operation.allowed_task_refs
    ):
        _fail(
            owner=CompilationOwner.PROGRAM,
            code="operation_argument_unsupported",
            message=(
                "run_stage.v1 requires literal task_ref/stage_id arguments and accepts only "
                "an output-derived upstream_receipts argument"
            ),
            subject_ids=(node.node_id, *tuple(sorted(names))),
        )


def _validate_legacy_finalize_task(
    *,
    node: ActionNode | FanoutNode | VerifyNode,
    names: set[str],
    operation: ProgramOperationSpec,
) -> None:
    arguments = {argument.name: argument for argument in node.arguments}
    task_ref = _literal_string(arguments.get("task_ref"))
    stage_receipts = arguments.get("stage_receipts")
    stage_receipt_value = stage_receipts.value if stage_receipts is not None else None
    if (
        not isinstance(node, ActionNode)
        or names != {"task_ref", "stage_receipts"}
        or task_ref is None
        or task_ref not in operation.allowed_task_refs
        or not isinstance(stage_receipt_value, OutputValue)
        or stage_receipt_value.ref.output_port not in {"stage_receipt", "result"}
    ):
        _fail(
            owner=CompilationOwner.PROGRAM,
            code="operation_argument_unsupported",
            message="finalize_task.v1 requires a literal task_ref and output-derived stage_receipts argument",
            subject_ids=(node.node_id, *tuple(sorted(names))),
        )


def _validate_legacy_run_batch(
    *,
    node: ActionNode | FanoutNode | VerifyNode,
    names: set[str],
) -> None:
    if isinstance(node, FanoutNode):
        valid = node.item_argument == "task_ref" and not names
    else:
        valid = len(names) <= 1 and names.issubset({"task_ref", "task_refs"})
    if not valid:
        _fail(
            owner=CompilationOwner.PROGRAM,
            code="operation_argument_unsupported",
            message=(
                "run_batch.v1 accepts one optional task_ref/task_refs selection; fanout must bind exactly task_ref"
            ),
            subject_ids=(node.node_id, *tuple(sorted(names))),
        )


def _operation_definition_for_compilation(
    *,
    registry: KernelRuntimeRegistry,
    operation: ProgramOperationSpec,
) -> KernelOperationDefinition | None:
    """Resolve migrated compiler metadata from the same exact registry capability."""
    definition = registry.operation_definition(operation.operation_id)
    if definition is None:
        if not registry.is_legacy_definition_free:
            _fail(
                owner=CompilationOwner.KERNEL,
                code="operation_definition_missing",
                message=("fixed-K operation lacks its phase-neutral definition: " + operation.operation_id),
                subject_ids=(operation.operation_id,),
            )
        return None
    if operation.capability_ref != definition.capability.ref:
        _fail(
            owner=CompilationOwner.KERNEL,
            code="operation_definition_mismatch",
            message=(
                "compiled harness operation differs from its installed kernel definition: " + operation.operation_id
            ),
            subject_ids=(operation.operation_id,),
        )
    return definition


def _validate_definition_arguments(
    node: ActionNode | FanoutNode | VerifyNode,
    *,
    definition: KernelOperationDefinition,
    operation: ProgramOperationSpec,
    profile: ProgramCompilationProfile,
) -> None:
    names = {argument.name for argument in node.arguments}
    if definition.argument_policy is KernelOperationArgumentPolicy.NO_ARGUMENTS_ACTION:
        _validate_definition_no_argument_action(
            node=node,
            names=names,
            definition=definition,
        )
        return
    if definition.argument_policy not in {
        KernelOperationArgumentPolicy.DECLARED_ARGUMENTS_ACTION,
        KernelOperationArgumentPolicy.DECLARED_ARGUMENTS_ACTION_OR_FANOUT,
    }:
        raise AssertionError(f"unhandled kernel operation argument policy: {definition.argument_policy}")
    if _is_monolithic_argument_exception(
        node=node,
        definition=definition,
        profile=profile,
    ):
        return
    if isinstance(node, FanoutNode):
        _validate_definition_fanout(
            node=node,
            names=names,
            definition=definition,
        )
        return
    if not _definition_action_arguments_valid(
        node=node,
        definition=definition,
        operation=operation,
        names=names,
    ):
        _fail_definition_arguments(node=node, names=names, definition=definition)


def _validate_definition_no_argument_action(
    *,
    node: ActionNode | FanoutNode | VerifyNode,
    names: set[str],
    definition: KernelOperationDefinition,
) -> None:
    if names or not isinstance(node, ActionNode):
        _fail_definition_arguments(node=node, names=names, definition=definition)


def _is_monolithic_argument_exception(
    *,
    node: ActionNode | FanoutNode | VerifyNode,
    definition: KernelOperationDefinition,
    profile: ProgramCompilationProfile,
) -> bool:
    return (
        definition.allow_monolithic_without_arguments
        and profile is ProgramCompilationProfile.MONOLITHIC_INCUMBENT
        and isinstance(node, ActionNode)
        and not node.arguments
        and not node.depends_on
    )


def _validate_definition_fanout(
    *,
    node: FanoutNode,
    names: set[str],
    definition: KernelOperationDefinition,
) -> None:
    valid = (
        definition.argument_policy is KernelOperationArgumentPolicy.DECLARED_ARGUMENTS_ACTION_OR_FANOUT
        and not names
        and node.item_argument == definition.fanout_item_argument
    )
    if not valid:
        _fail_definition_arguments(node=node, names=names, definition=definition)


def _definition_action_arguments_valid(
    *,
    node: ActionNode | VerifyNode,
    definition: KernelOperationDefinition,
    operation: ProgramOperationSpec,
    names: set[str],
) -> bool:
    arguments = {argument.name: argument for argument in node.arguments}
    declared_names = {argument.name for argument in definition.arguments}
    required_names = {argument.name for argument in definition.arguments if argument.required}
    valid = (
        isinstance(node, ActionNode)
        and len(arguments) == len(node.arguments)
        and required_names.issubset(names)
        and names.issubset(declared_names)
        and (definition.maximum_arguments is None or len(names) <= definition.maximum_arguments)
    )
    if not valid:
        return False
    return all(
        _definition_argument_valid(
            argument=arguments.get(argument_spec.name),
            argument_spec=argument_spec,
            operation=operation,
        )
        for argument_spec in definition.arguments
    )


def _definition_argument_valid(
    *,
    argument: ProgramArgument | None,
    argument_spec: KernelOperationArgumentSpec,
    operation: ProgramOperationSpec,
) -> bool:
    if argument is None:
        return True
    if argument_spec.source is KernelOperationArgumentSource.LITERAL_STRING:
        literal = _literal_string(argument)
        return literal is not None and (
            not argument_spec.restrict_to_allowed_task_refs or literal in operation.allowed_task_refs
        )
    if argument_spec.source is KernelOperationArgumentSource.OUTPUT:
        return isinstance(argument.value, OutputValue) and argument.value.ref.output_port in argument_spec.output_ports
    return True


def _fail_definition_arguments(
    *,
    node: ActionNode | FanoutNode | VerifyNode,
    names: set[str],
    definition: KernelOperationDefinition,
) -> None:
    _fail(
        owner=CompilationOwner.PROGRAM,
        code="operation_argument_unsupported",
        message=definition.argument_error_message,
        subject_ids=(node.node_id, *tuple(sorted(names))),
    )


def _literal_string(argument: ProgramArgument | None) -> str | None:
    if argument is None or not isinstance(argument.value, LiteralValue):
        return None
    value = argument.value.value
    return value if isinstance(value, str) and value.strip() else None


def _validate_operation_retry_taxonomy(
    *,
    operation: ProgramOperationSpec,
    runtime: ProgramOperationRuntime,
) -> None:
    prohibited = prohibited_retry_safe_error_codes(runtime.retry_safe_error_codes)
    if prohibited:
        _fail(
            owner=CompilationOwner.KERNEL,
            code="program_operation_retry_taxonomy_unsafe",
            message="fixed-K operation declares prohibited retry-safe error codes",
            subject_ids=(operation.operation_id, *prohibited),
        )
    if operation.retry_safe_error_codes != runtime.retry_safe_error_codes or operation.supports_retry is not bool(
        runtime.retry_safe_error_codes
    ):
        _fail(
            owner=CompilationOwner.HARNESS,
            code="operation_retry_taxonomy_mismatch",
            message=f"operation retry taxonomy differs from the installed fixed-K primitive: {operation.operation_id}",
            subject_ids=(operation.operation_id,),
        )
