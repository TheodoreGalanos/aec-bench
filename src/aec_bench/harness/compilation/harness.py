# ABOUTME: Compiles one task-specific harness recipe against the exact installed fixed kernel.
# ABOUTME: Materializes the closed executable operation surface without changing operation order.

from aec_bench.contracts.harness_instance import (
    AgentBindingConfig,
    CompiledHarnessBinding,
    CompiledHarnessInstance,
    ComputeBindingConfig,
    HarnessCompileRequest,
    ProgramOperationScope,
    ProgramOperationSpec,
    ProgramSurface,
    ResultImportBindingConfig,
    TaskSourceBindingConfig,
    VerificationBindingConfig,
    VerificationPlacement,
    VerificationStage,
)
from aec_bench.harness.kernel_catalogue import (
    KernelRuntimeRegistry,
    KernelRuntimeRegistryError,
)

from .bindings import (
    _configurations,
    _single_configuration,
    _validate_execution_bearing_harness,
)
from .diagnostics import CompilationOwner, _fail
from .operations import _resolve_program_operation_abi


def compile_harness_instance(
    request: HarnessCompileRequest,
    *,
    registry: KernelRuntimeRegistry,
) -> CompiledHarnessInstance:
    """Resolve every Hx recipe binding against one exact installed fixed kernel."""
    if request.kernel_ref != registry.manifest.ref:
        _fail(
            owner=CompilationOwner.KERNEL,
            code="kernel_reference_mismatch",
            message="harness compile request does not target the installed fixed kernel",
            subject_ids=(request.kernel_ref.kernel_id,),
        )
    if request.recipe.recursion_policy.enabled:
        _fail(
            owner=CompilationOwner.KERNEL,
            code="recursive_program_operation_unavailable",
            message="the installed fixed kernel exposes no recursive program operation",
            subject_ids=(registry.manifest.kernel_id,),
        )

    compiled_bindings: list[CompiledHarnessBinding] = []
    for binding in request.recipe.bindings:
        try:
            primitive = registry.resolve(binding.capability_ref)
        except KernelRuntimeRegistryError as exc:
            _fail(
                owner=CompilationOwner.HARNESS,
                code="capability_not_in_fixed_kernel",
                message=str(exc),
                subject_ids=(binding.binding_id, binding.capability_ref.capability_id),
            )
        compiled_bindings.append(
            CompiledHarnessBinding(
                binding_id=binding.binding_id,
                capability_ref=primitive.spec.ref,
                capability_kind=primitive.spec.kind,
                depends_on=binding.depends_on,
                topology_role=binding.topology_role,
                contract_ids=binding.contract_ids,
                configuration=binding.configuration,
            )
        )

    task_binding, task_configuration = _single_configuration(
        compiled_bindings,
        TaskSourceBindingConfig,
        role="task source",
    )
    agent_binding, _ = _single_configuration(compiled_bindings, AgentBindingConfig, role="agent")
    _, compute_configuration = _single_configuration(
        compiled_bindings,
        ComputeBindingConfig,
        role="compute",
    )
    _single_configuration(compiled_bindings, ResultImportBindingConfig, role="result import")
    verification_bindings = _configurations(compiled_bindings, VerificationBindingConfig)
    if len(verification_bindings) > 1:
        _fail(
            owner=CompilationOwner.HARNESS,
            code="ambiguous_verifier_binding",
            message="initial Harbor harness compilation supports at most one verifier binding",
            subject_ids=tuple(sorted(binding.binding_id for binding, _ in verification_bindings)),
        )
    _validate_execution_bearing_harness(
        bindings=tuple(compiled_bindings),
        contracts=request.recipe.contracts,
        registry=registry,
        task_binding=task_binding,
        agent_binding=agent_binding,
        compute_binding=_single_configuration(
            compiled_bindings,
            ComputeBindingConfig,
            role="compute",
        )[0],
        verification_bindings=tuple(binding for binding, _ in verification_bindings),
        import_binding=_single_configuration(
            compiled_bindings,
            ResultImportBindingConfig,
            role="result import",
        )[0],
    )

    (
        operation_id,
        operation_capability,
        operation_runtime,
        operation_input_schema_ref,
        operation_output_schema_ref,
    ) = _resolve_program_operation_abi(
        registry=registry,
        operation_id="run_batch.v1",
        capability_id="aecbench.operation.harbor.run-batch",
        input_schema_ref="aecbench://run-batch-selection/v1",
        output_schema_ref="aecbench://trial-record-set/v1",
    )
    operation_retry_codes = operation_runtime.retry_safe_error_codes
    verifier_placements = tuple(
        VerificationPlacement(
            binding_id=binding.binding_id,
            stage=VerificationStage.AFTER_OPERATION,
            required=configuration.required,
        )
        for binding, configuration in verification_bindings
        if configuration.enabled
    )
    operation = ProgramOperationSpec(
        operation_id=operation_id,
        capability_ref=operation_capability.ref,
        input_schema_ref=operation_input_schema_ref,
        output_schema_ref=operation_output_schema_ref,
        binding_ids=tuple(binding.binding_id for binding in compiled_bindings),
        contract_ids=tuple(contract.contract_id for contract in request.recipe.contracts),
        allowed_task_refs=task_configuration.task_refs,
        max_parallelism=min(compute_configuration.max_concurrency, request.recipe.budget.max_parallelism),
        supports_retry=bool(operation_retry_codes),
        retry_safe_error_codes=operation_retry_codes,
        supports_recursion=False,
        verifier_placements=verifier_placements,
    )
    (
        stage_operation_id,
        stage_capability,
        stage_runtime,
        stage_input_schema_ref,
        stage_output_schema_ref,
    ) = _resolve_program_operation_abi(
        registry=registry,
        operation_id="run_stage.v1",
        capability_id="aecbench.operation.harbor.run-stage",
        input_schema_ref="aecbench://run-stage-selection/v1",
        output_schema_ref="aecbench://stage-execution-receipt-ref/v1",
    )
    stage_binding_ids = tuple(
        binding.binding_id
        for binding in compiled_bindings
        if not isinstance(
            binding.configuration,
            VerificationBindingConfig | ResultImportBindingConfig,
        )
    )
    stage_operation = ProgramOperationSpec(
        operation_id=stage_operation_id,
        capability_ref=stage_capability.ref,
        input_schema_ref=stage_input_schema_ref,
        output_schema_ref=stage_output_schema_ref,
        binding_ids=stage_binding_ids,
        contract_ids=tuple(contract.contract_id for contract in request.recipe.contracts),
        allowed_task_refs=task_configuration.task_refs,
        max_parallelism=min(
            compute_configuration.max_concurrency,
            request.recipe.budget.max_parallelism,
        ),
        supports_retry=bool(stage_runtime.retry_safe_error_codes),
        retry_safe_error_codes=stage_runtime.retry_safe_error_codes,
    )
    (
        finalize_operation_id,
        finalize_capability,
        finalize_runtime,
        finalize_input_schema_ref,
        finalize_output_schema_ref,
    ) = _resolve_program_operation_abi(
        registry=registry,
        operation_id="finalize_task.v1",
        capability_id="aecbench.operation.harbor.finalize-task",
        input_schema_ref="aecbench://finalize-task-selection/v1",
        output_schema_ref="aecbench://trial-record-set/v1",
    )
    finalize_operation = ProgramOperationSpec(
        operation_id=finalize_operation_id,
        capability_ref=finalize_capability.ref,
        input_schema_ref=finalize_input_schema_ref,
        output_schema_ref=finalize_output_schema_ref,
        binding_ids=tuple(binding.binding_id for binding in compiled_bindings),
        contract_ids=tuple(contract.contract_id for contract in request.recipe.contracts),
        allowed_task_refs=task_configuration.task_refs,
        max_parallelism=min(
            compute_configuration.max_concurrency,
            request.recipe.budget.max_parallelism,
        ),
        supports_retry=bool(finalize_runtime.retry_safe_error_codes),
        retry_safe_error_codes=finalize_runtime.retry_safe_error_codes,
        verifier_placements=tuple(
            VerificationPlacement(
                binding_id=binding.binding_id,
                stage=VerificationStage.FINAL,
                required=configuration.required,
            )
            for binding, configuration in verification_bindings
            if configuration.enabled
        ),
    )
    (
        proposal_session_operation_id,
        proposal_session_capability,
        _,
        proposal_session_input_schema_ref,
        proposal_session_output_schema_ref,
    ) = _resolve_program_operation_abi(
        registry=registry,
        operation_id="run_proposal_session.v1",
        capability_id="aecbench.operation.proposal.run-session",
        input_schema_ref="aecbench://proposal-session-internal/v1",
        output_schema_ref="aecbench://proposal-session-receipt/v1",
    )
    proposal_session_operation = ProgramOperationSpec(
        operation_id=proposal_session_operation_id,
        capability_ref=proposal_session_capability.ref,
        input_schema_ref=proposal_session_input_schema_ref,
        output_schema_ref=proposal_session_output_schema_ref,
        binding_ids=tuple(binding.binding_id for binding in compiled_bindings),
        contract_ids=tuple(contract.contract_id for contract in request.recipe.contracts),
        allowed_task_refs=task_configuration.task_refs,
        max_parallelism=1,
    )
    (
        semantic_subtask_operation_id,
        semantic_subtask_capability,
        _,
        semantic_subtask_input_schema_ref,
        semantic_subtask_output_schema_ref,
    ) = _resolve_program_operation_abi(
        registry=registry,
        operation_id="run_semantic_subtask.v1",
        capability_id="aecbench.operation.proposal.run-semantic-subtask",
        input_schema_ref="aecbench://semantic-subtask-internal/v1",
        output_schema_ref="aecbench://semantic-subtask-result/v1",
    )
    semantic_subtask_operation = ProgramOperationSpec(
        operation_id=semantic_subtask_operation_id,
        capability_ref=semantic_subtask_capability.ref,
        input_schema_ref=semantic_subtask_input_schema_ref,
        output_schema_ref=semantic_subtask_output_schema_ref,
        binding_ids=stage_binding_ids,
        contract_ids=tuple(contract.contract_id for contract in request.recipe.contracts),
        allowed_task_refs=task_configuration.task_refs,
        max_parallelism=1,
        required_compilation_scope=ProgramOperationScope.PROPOSAL_SESSION_INTERNAL,
    )
    (
        subtask_check_operation_id,
        subtask_check_capability,
        _,
        subtask_check_input_schema_ref,
        subtask_check_output_schema_ref,
    ) = _resolve_program_operation_abi(
        registry=registry,
        operation_id="check_subtask_contract.v1",
        capability_id="aecbench.operation.proposal.check-subtask-contract",
        input_schema_ref="aecbench://subtask-contract-check-selection/v1",
        output_schema_ref="aecbench://subtask-contract-check-ref/v1",
    )
    subtask_check_operation = ProgramOperationSpec(
        operation_id=subtask_check_operation_id,
        capability_ref=subtask_check_capability.ref,
        input_schema_ref=subtask_check_input_schema_ref,
        output_schema_ref=subtask_check_output_schema_ref,
        binding_ids=(task_binding.binding_id,),
        contract_ids=tuple(contract.contract_id for contract in request.recipe.contracts),
        allowed_task_refs=task_configuration.task_refs,
        max_parallelism=1,
        required_compilation_scope=ProgramOperationScope.PROPOSAL_SESSION_INTERNAL,
    )
    (
        proposal_finalizer_operation_id,
        proposal_finalizer_capability,
        _,
        proposal_finalizer_input_schema_ref,
        proposal_finalizer_output_schema_ref,
    ) = _resolve_program_operation_abi(
        registry=registry,
        operation_id="finalize_proposed_plan.v1",
        capability_id="aecbench.operation.proposal.finalize-proposed-plan",
        input_schema_ref="aecbench://finalize-proposed-plan-selection/v1",
        output_schema_ref="aecbench://trial-record-set/v1",
    )
    proposal_finalizer_operation = ProgramOperationSpec(
        operation_id=proposal_finalizer_operation_id,
        capability_ref=proposal_finalizer_capability.ref,
        input_schema_ref=proposal_finalizer_input_schema_ref,
        output_schema_ref=proposal_finalizer_output_schema_ref,
        binding_ids=tuple(binding.binding_id for binding in compiled_bindings),
        contract_ids=tuple(contract.contract_id for contract in request.recipe.contracts),
        allowed_task_refs=task_configuration.task_refs,
        max_parallelism=1,
        required_compilation_scope=ProgramOperationScope.PROPOSAL_SESSION_INTERNAL,
        verifier_placements=tuple(
            VerificationPlacement(
                binding_id=binding.binding_id,
                stage=VerificationStage.FINAL,
                required=configuration.required,
            )
            for binding, configuration in verification_bindings
            if configuration.enabled
        ),
    )
    (
        enumeration_operation_id,
        enumeration_capability,
        enumeration_runtime,
        enumeration_input_schema_ref,
        enumeration_output_schema_ref,
    ) = _resolve_program_operation_abi(
        registry=registry,
        operation_id="enumerate_tasks.v1",
        capability_id="aecbench.operation.tasks.enumerate",
        input_schema_ref="aecbench://empty/v1",
        output_schema_ref="aecbench://task-ref-set/v1",
    )
    enumeration_retry_codes = enumeration_runtime.retry_safe_error_codes
    enumeration_operation = ProgramOperationSpec(
        operation_id=enumeration_operation_id,
        capability_ref=enumeration_capability.ref,
        input_schema_ref=enumeration_input_schema_ref,
        output_schema_ref=enumeration_output_schema_ref,
        binding_ids=(task_binding.binding_id,),
        contract_ids=task_binding.contract_ids,
        allowed_task_refs=task_configuration.task_refs,
        max_parallelism=1,
        supports_retry=bool(enumeration_retry_codes),
        retry_safe_error_codes=enumeration_retry_codes,
    )
    instance_id = f"hx.{request.recipe.recipe_id}.{request.recipe.version}"
    return CompiledHarnessInstance(
        instance_id=instance_id,
        kernel_ref=registry.manifest.ref,
        source_recipe_ref=request.recipe.ref,
        contracts=request.recipe.contracts,
        budget=request.recipe.budget,
        recursion_policy=request.recipe.recursion_policy,
        bindings=tuple(compiled_bindings),
        program_surface=ProgramSurface(
            surface_id=f"surface.{request.recipe.recipe_id}.v1",
            operations=(
                enumeration_operation,
                operation,
                stage_operation,
                finalize_operation,
                proposal_session_operation,
                semantic_subtask_operation,
                subtask_check_operation,
                proposal_finalizer_operation,
            ),
        ),
    )
