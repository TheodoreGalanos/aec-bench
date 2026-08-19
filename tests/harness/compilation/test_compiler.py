# ABOUTME: Tests deterministic compilation from fixed K plus Hx and px into executable run plans.
# ABOUTME: Verifies exact capability resolution, operation pinning, diagnostics, and real task snapshots.

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aec_bench.contracts.execution_program import (
    ActionNode,
    ExecutionProgram,
    FanoutNode,
    JoinNode,
    LiteralValue,
    OutputValue,
    ProgramArgument,
    ProgramOutputRef,
    RetryPolicy,
    StopNode,
    StopOutcome,
    VerifyNode,
)
from aec_bench.contracts.harness_instance import (
    AgentBindingConfig,
    CompiledHarnessInstance,
    ComputeBindingConfig,
    ContextBindingConfig,
    ContextSelectionStrategy,
    HarnessBindingSpec,
    HarnessCompileRequest,
    HarnessContractEnforcement,
    HarnessContractKind,
    HarnessContractSpec,
    HarnessRecipe,
    HarnessRecursionPolicy,
    HarnessTopologyRole,
    ProgramOperationScope,
    ResultImportBindingConfig,
    TaskSourceBindingConfig,
    ToolAccessMode,
    ToolBindingConfig,
    VerificationBindingConfig,
)
from aec_bench.contracts.harness_kernel import KernelCapabilityRef
from aec_bench.contracts.task_review_snapshot import ReviewSnapshot
from aec_bench.harness.compilation import (
    CompilationError,
    CompilationOwner,
    _operation_definition_for_compilation,
    compile_execution_program,
    compile_harness_instance,
    compile_run_plan,
)
from aec_bench.harness.kernel_catalogue import (
    KernelRuntimePrimitive,
    KernelRuntimeRegistry,
    ProgramOperationRuntime,
    default_kernel_registry,
)


def test_harness_compiler_resolves_every_binding_into_one_execution_bearing_surface() -> None:
    registry = default_kernel_registry()
    recipe = _recipe(registry, task_id="civil/calculation/adaptive")

    harness = compile_harness_instance(
        HarnessCompileRequest(
            request_id="compile-adaptive",
            kernel_ref=registry.manifest.ref,
            recipe=recipe,
        ),
        registry=registry,
    )

    operation = harness.program_surface.operation("run_batch.v1")
    assert operation is not None
    batch_definition = registry.operation_definition("run_batch.v1")
    assert batch_definition is not None
    assert (
        _operation_definition_for_compilation(
            registry=registry,
            operation=operation,
        )
        == batch_definition
    )
    assert operation.operation_id == batch_definition.operation_id
    assert operation.capability_ref == batch_definition.capability.ref
    assert operation.input_schema_ref == batch_definition.input_schema_ref
    assert operation.output_schema_ref == batch_definition.output_schema_ref
    assert "content_sha256" not in operation.model_dump(mode="json")
    assert set(operation.binding_ids) == {binding.binding_id for binding in harness.bindings}
    assert operation.allowed_task_refs == ("civil/calculation/adaptive",)
    assert operation.max_parallelism == 2
    assert operation.supports_retry is False
    assert operation.retry_safe_error_codes == ()
    assert operation.verifier_placements[0].binding_id == "verify"
    assert harness.kernel_ref == registry.manifest.ref
    assert harness.source_recipe_ref == recipe.ref
    enumerate_operation = harness.program_surface.operation("enumerate_tasks.v1")
    assert enumerate_operation is not None
    enumerate_definition = registry.operation_definition("enumerate_tasks.v1")
    assert enumerate_definition is not None
    assert (
        _operation_definition_for_compilation(
            registry=registry,
            operation=enumerate_operation,
        )
        == enumerate_definition
    )
    assert enumerate_operation.operation_id == enumerate_definition.operation_id
    assert enumerate_operation.capability_ref == enumerate_definition.capability.ref
    assert enumerate_operation.input_schema_ref == enumerate_definition.input_schema_ref
    assert enumerate_operation.output_schema_ref == enumerate_definition.output_schema_ref
    assert "content_sha256" not in enumerate_operation.model_dump(mode="json")
    assert enumerate_operation.binding_ids == ("tasks",)
    assert enumerate_operation.allowed_task_refs == ("civil/calculation/adaptive",)
    run_stage = harness.program_surface.operation("run_stage.v1")
    assert run_stage is not None
    stage_definition = registry.operation_definition("run_stage.v1")
    assert stage_definition is not None
    assert (
        _operation_definition_for_compilation(
            registry=registry,
            operation=run_stage,
        )
        == stage_definition
    )
    assert run_stage.operation_id == stage_definition.operation_id
    assert run_stage.capability_ref == stage_definition.capability.ref
    assert run_stage.input_schema_ref == stage_definition.input_schema_ref
    assert run_stage.output_schema_ref == stage_definition.output_schema_ref
    assert "content_sha256" not in run_stage.model_dump(mode="json")
    assert set(run_stage.binding_ids) == {"tasks", "context", "tools", "agent", "compute"}
    assert run_stage.verifier_placements == ()
    finalize_task = harness.program_surface.operation("finalize_task.v1")
    assert finalize_task is not None
    finalize_definition = registry.operation_definition("finalize_task.v1")
    assert finalize_definition is not None
    assert (
        _operation_definition_for_compilation(
            registry=registry,
            operation=finalize_task,
        )
        == finalize_definition
    )
    assert finalize_task.operation_id == finalize_definition.operation_id
    assert finalize_task.capability_ref == finalize_definition.capability.ref
    assert finalize_task.input_schema_ref == finalize_definition.input_schema_ref
    assert finalize_task.output_schema_ref == finalize_definition.output_schema_ref
    assert "content_sha256" not in finalize_task.model_dump(mode="json")
    assert set(finalize_task.binding_ids) == {binding.binding_id for binding in harness.bindings}
    assert finalize_task.verifier_placements[0].binding_id == "verify"


def test_harness_compiler_exports_the_fixed_sequential_k9_proposal_surface() -> None:
    registry = default_kernel_registry()
    harness = _compiled_harness(registry)

    expected_capabilities = {
        "run_proposal_session.v1": "aecbench.operation.proposal.run-session",
        "run_semantic_subtask.v1": "aecbench.operation.proposal.run-semantic-subtask",
        "check_subtask_contract.v1": "aecbench.operation.proposal.check-subtask-contract",
        "finalize_proposed_plan.v1": "aecbench.operation.proposal.finalize-proposed-plan",
    }
    operations = {
        operation_id: harness.program_surface.operation(operation_id) for operation_id in expected_capabilities
    }

    assert all(operation is not None for operation in operations.values())
    for operation_id, capability_id in expected_capabilities.items():
        operation = operations[operation_id]
        assert operation is not None
        assert operation.capability_ref == registry.capability(capability_id).ref
        assert operation.allowed_task_refs == ("civil/calculation/adaptive",)
        assert operation.max_parallelism == 1
        assert operation.supports_retry is False
        assert operation.retry_safe_error_codes == ()
        assert operation.supports_recursion is False

    all_binding_ids = {binding.binding_id for binding in harness.bindings}
    execution_binding_ids = all_binding_ids - {"verify", "import"}
    assert set(operations["run_proposal_session.v1"].binding_ids) == all_binding_ids
    assert set(operations["run_semantic_subtask.v1"].binding_ids) == execution_binding_ids
    assert operations["check_subtask_contract.v1"].binding_ids == ("tasks",)
    assert set(operations["finalize_proposed_plan.v1"].binding_ids) == all_binding_ids
    for operation_id in expected_capabilities:
        operation = operations[operation_id]
        assert operation is not None
        definition = registry.operation_definition(operation_id)
        assert definition is not None
        assert (
            _operation_definition_for_compilation(
                registry=registry,
                operation=operation,
            )
            == definition
        )
        assert operation.operation_id == definition.operation_id
        assert operation.capability_ref == definition.capability.ref
        assert operation.input_schema_ref == definition.input_schema_ref
        assert operation.output_schema_ref == definition.output_schema_ref
        assert "content_sha256" not in operation.model_dump(mode="json")


def test_legacy_registry_without_definitions_preserves_migrated_v1_harness_abis() -> None:
    current = default_kernel_registry()
    legacy = KernelRuntimeRegistry(
        manifest=current.manifest,
        primitives=current.primitives,
        package_fingerprint=current.package_fingerprint,
        operation_definitions=(),
    )

    current_harness = _compiled_harness(current)
    legacy_harness = _compiled_harness(legacy)

    for operation_id in (
        "enumerate_tasks.v1",
        "check_subtask_contract.v1",
        "finalize_proposed_plan.v1",
        "finalize_task.v1",
        "run_batch.v1",
        "run_proposal_session.v1",
        "run_semantic_subtask.v1",
        "run_stage.v1",
    ):
        current_operation = current_harness.program_surface.operation(operation_id)
        legacy_operation = legacy_harness.program_surface.operation(operation_id)
        assert current_operation is not None
        assert legacy_operation is not None
        assert legacy.operation_definition(operation_id) is None
        assert current_operation == legacy_operation
        assert current_operation.model_dump_json() == legacy_operation.model_dump_json()
        assert (
            _operation_definition_for_compilation(
                registry=legacy,
                operation=legacy_operation,
            )
            is None
        )


def test_harness_compiler_sources_retry_taxonomy_from_the_fixed_kernel_primitive() -> None:
    registry = _registry_with_retryable_run_batch(
        default_kernel_registry(),
        retry_safe_error_codes=("pre_dispatch_capacity_timeout",),
    )

    harness = _compiled_harness(registry)

    operation = harness.program_surface.operation("run_batch.v1")
    assert operation is not None
    assert operation.supports_retry is True
    assert operation.retry_safe_error_codes == ("pre_dispatch_capacity_timeout",)


def test_program_compiler_accepts_task_enumeration_fanout_against_fixed_harness_surface() -> None:
    registry = default_kernel_registry()
    harness = _compiled_harness(registry)
    source = ExecutionProgram(
        program_id="px-decomposed",
        version="1.0.0",
        harness_ref=harness.ref,
        nodes=(
            ActionNode(node_id="enumerate", operation_id="enumerate_tasks.v1"),
            FanoutNode(
                node_id="run-each",
                depends_on=("enumerate",),
                operation_id="run_batch.v1",
                items=ProgramOutputRef(node_id="enumerate", output_port="tasks"),
                item_argument="task_ref",
                max_parallelism=2,
            ),
            StopNode(
                node_id="stop",
                depends_on=("run-each",),
                outcome=StopOutcome.SUCCEEDED,
                result=ProgramOutputRef(node_id="run-each", output_port="result"),
            ),
        ),
    )

    compiled = compile_execution_program(source, harness=harness, registry=registry)

    assert compiled.topological_order == ("enumerate", "run-each", "stop")
    assert tuple(reference.operation_id for reference in compiled.operation_refs) == (
        "enumerate_tasks.v1",
        "run_batch.v1",
    )


def test_program_compiler_accepts_the_closed_internal_k9_sequence() -> None:
    registry = default_kernel_registry()
    harness = _compiled_harness(registry)
    source = ExecutionProgram(
        program_id="px-k9-internal",
        version="1.0.0",
        harness_ref=harness.ref,
        nodes=(
            ActionNode(
                node_id="analyse",
                operation_id="run_semantic_subtask.v1",
            ),
            ActionNode(
                node_id="check",
                depends_on=("analyse",),
                operation_id="check_subtask_contract.v1",
                arguments=(
                    ProgramArgument(
                        name="subject",
                        value=OutputValue(
                            ref=ProgramOutputRef(
                                node_id="analyse",
                                output_port="result",
                            )
                        ),
                    ),
                ),
            ),
            ActionNode(
                node_id="finalize",
                depends_on=("check",),
                operation_id="finalize_proposed_plan.v1",
                arguments=(
                    ProgramArgument(
                        name="findings",
                        value=OutputValue(
                            ref=ProgramOutputRef(
                                node_id="check",
                                output_port="result",
                            )
                        ),
                    ),
                ),
            ),
            StopNode(
                node_id="stop",
                depends_on=("finalize",),
                outcome=StopOutcome.SUCCEEDED,
                result=ProgramOutputRef(
                    node_id="finalize",
                    output_port="result",
                ),
            ),
        ),
    )

    compiled = compile_execution_program(
        source,
        harness=harness,
        registry=registry,
        compilation_scope=ProgramOperationScope.PROPOSAL_SESSION_INTERNAL,
    )

    assert compiled.topological_order == (
        "analyse",
        "check",
        "finalize",
        "stop",
    )
    assert tuple(reference.operation_id for reference in compiled.operation_refs) == (
        "check_subtask_contract.v1",
        "finalize_proposed_plan.v1",
        "run_semantic_subtask.v1",
    )


def test_program_compiler_accepts_the_argument_free_k9_session_boundary() -> None:
    registry = default_kernel_registry()
    harness = _compiled_harness(registry)
    source = ExecutionProgram(
        program_id="px-k9-session",
        version="1.0.0",
        harness_ref=harness.ref,
        nodes=(
            ActionNode(
                node_id="session",
                operation_id="run_proposal_session.v1",
            ),
            StopNode(
                node_id="stop",
                depends_on=("session",),
                outcome=StopOutcome.SUCCEEDED,
                result=ProgramOutputRef(
                    node_id="session",
                    output_port="session_receipt",
                ),
            ),
        ),
    )

    compiled = compile_execution_program(
        source,
        harness=harness,
        registry=registry,
    )

    assert compiled.topological_order == ("session", "stop")
    assert tuple(reference.operation_id for reference in compiled.operation_refs) == ("run_proposal_session.v1",)


@pytest.mark.parametrize(
    ("operation_id", "arguments"),
    (
        (
            "run_proposal_session.v1",
            (
                ProgramArgument(
                    name="session_plan",
                    value=LiteralValue(value="candidate-controlled"),
                ),
            ),
        ),
        (
            "run_semantic_subtask.v1",
            (
                ProgramArgument(
                    name="source_scope",
                    value=LiteralValue(value="candidate-controlled"),
                ),
            ),
        ),
        ("check_subtask_contract.v1", ()),
        (
            "check_subtask_contract.v1",
            (
                ProgramArgument(
                    name="subject",
                    value=LiteralValue(value="candidate-controlled"),
                ),
            ),
        ),
        ("finalize_proposed_plan.v1", ()),
        (
            "finalize_proposed_plan.v1",
            (
                ProgramArgument(
                    name="findings",
                    value=LiteralValue(value="candidate-controlled"),
                ),
            ),
        ),
    ),
)
def test_program_compiler_rejects_arguments_outside_the_closed_k9_internal_abi(
    operation_id: str,
    arguments: tuple[ProgramArgument, ...],
) -> None:
    registry = default_kernel_registry()
    harness = _compiled_harness(registry)
    source = ExecutionProgram(
        program_id=f"px-invalid-{operation_id}",
        version="1.0.0",
        harness_ref=harness.ref,
        nodes=(
            ActionNode(
                node_id="run",
                operation_id=operation_id,
                arguments=arguments,
            ),
            StopNode(
                node_id="stop",
                depends_on=("run",),
                outcome=StopOutcome.FAILED,
            ),
        ),
    )

    with pytest.raises(CompilationError) as captured:
        compile_execution_program(
            source,
            harness=harness,
            registry=registry,
            compilation_scope=ProgramOperationScope.PROPOSAL_SESSION_INTERNAL,
        )

    assert captured.value.diagnostic.owner is CompilationOwner.PROGRAM
    assert captured.value.diagnostic.code == "operation_argument_unsupported"


@pytest.mark.parametrize(
    "arguments",
    (
        (
            ProgramArgument(
                name="task_ref",
                value=LiteralValue(value="civil/calculation/not-allowed"),
            ),
            ProgramArgument(
                name="stage_receipts",
                value=OutputValue(
                    ref=ProgramOutputRef(
                        node_id="all-stages",
                        output_port="result",
                    )
                ),
            ),
        ),
        (
            ProgramArgument(
                name="task_ref",
                value=LiteralValue(value="civil/calculation/adaptive"),
            ),
            ProgramArgument(
                name="stage_receipts",
                value=LiteralValue(value="candidate-controlled"),
            ),
        ),
    ),
)
def test_program_compiler_rejects_arguments_outside_finalize_task_abi(
    arguments: tuple[ProgramArgument, ...],
) -> None:
    registry = default_kernel_registry()
    task_id = "civil/calculation/adaptive"
    harness = _compiled_harness(registry, task_id=task_id)
    source = _stage_program(harness=harness, task_id=task_id)
    invalid = ExecutionProgram(
        program_id=source.program_id,
        version=source.version,
        harness_ref=source.harness_ref,
        nodes=tuple(
            ActionNode(
                node_id=node.node_id,
                depends_on=node.depends_on,
                operation_id=node.operation_id,
                arguments=arguments,
            )
            if isinstance(node, ActionNode) and node.operation_id == "finalize_task.v1"
            else node
            for node in source.nodes
        ),
        limits=source.limits,
    )

    with pytest.raises(CompilationError) as captured:
        compile_execution_program(
            invalid,
            harness=harness,
            registry=registry,
        )

    assert captured.value.diagnostic.code == "operation_argument_unsupported"
    assert (
        captured.value.diagnostic.message
        == "finalize_task.v1 requires a literal task_ref and output-derived stage_receipts argument"
    )


def test_program_compiler_rejects_verify_node_without_a_subject_verifier_operation() -> None:
    registry = default_kernel_registry()
    harness = _compiled_harness(registry)
    source = ExecutionProgram(
        program_id="px-false-verifier",
        version="1.0.0",
        harness_ref=harness.ref,
        nodes=(
            ActionNode(node_id="run", operation_id="run_batch.v1"),
            VerifyNode(
                node_id="verify",
                depends_on=("run",),
                operation_id="run_batch.v1",
                subject=ProgramOutputRef(node_id="run", output_port="result"),
            ),
            StopNode(node_id="stop", depends_on=("verify",), outcome=StopOutcome.SUCCEEDED),
        ),
    )

    with pytest.raises(CompilationError) as captured:
        compile_execution_program(source, harness=harness, registry=registry)

    assert captured.value.diagnostic.owner is CompilationOwner.KERNEL
    assert captured.value.diagnostic.code == "verifier_subject_operation_unavailable"


def test_harness_compiler_rejects_unknown_or_tampered_kernel_capabilities() -> None:
    registry = default_kernel_registry()
    recipe = _recipe(registry, task_id="civil/calculation/adaptive")
    agent = recipe.binding("agent")
    assert agent is not None
    tampered = agent.model_copy(
        update={
            "capability_ref": KernelCapabilityRef(
                capability_id=agent.capability_ref.capability_id,
                version="0.0.0",
            )
        }
    )
    bindings = tuple(tampered if binding.binding_id == "agent" else binding for binding in recipe.bindings)
    invalid_recipe = HarnessRecipe(
        recipe_id=recipe.recipe_id,
        version=recipe.version,
        summary=recipe.summary,
        budget=recipe.budget,
        bindings=bindings,
    )

    with pytest.raises(CompilationError) as captured:
        compile_harness_instance(
            HarnessCompileRequest(
                request_id="compile-tampered",
                kernel_ref=registry.manifest.ref,
                recipe=invalid_recipe,
            ),
            registry=registry,
        )

    assert captured.value.diagnostic.owner is CompilationOwner.HARNESS
    assert captured.value.diagnostic.code == "capability_not_in_fixed_kernel"


def test_harness_compiler_rejects_context_strategy_not_implemented_by_fixed_k() -> None:
    registry = default_kernel_registry()
    recipe = _replace_configuration(
        _recipe(registry, task_id="civil/calculation/adaptive"),
        binding_id="context",
        configuration=ContextBindingConfig(
            source_ids=("workspace.system_prompt",),
            selection_strategy=ContextSelectionStrategy.RETRIEVAL,
            max_tokens=4_000,
        ),
    )

    with pytest.raises(CompilationError) as captured:
        compile_harness_instance(
            HarnessCompileRequest(
                request_id="compile-retrieval-context",
                kernel_ref=registry.manifest.ref,
                recipe=recipe,
            ),
            registry=registry,
        )

    assert captured.value.diagnostic.owner is CompilationOwner.HARNESS
    assert captured.value.diagnostic.code == "context_selection_strategy_unsupported"


def test_harness_compiler_rejects_task_tools_for_adapter_without_tool_control() -> None:
    registry = default_kernel_registry()
    recipe = _recipe(registry, task_id="civil/calculation/adaptive")
    agent = recipe.binding("agent")
    assert agent is not None
    direct_agent = agent.model_copy(update={"capability_ref": registry.capability("aecbench.adapter.direct").ref})
    recipe = _replace_binding(recipe, direct_agent)

    with pytest.raises(CompilationError) as captured:
        compile_harness_instance(
            HarnessCompileRequest(
                request_id="compile-direct-tools",
                kernel_ref=registry.manifest.ref,
                recipe=recipe,
            ),
            registry=registry,
        )

    assert captured.value.diagnostic.owner is CompilationOwner.HARNESS
    assert captured.value.diagnostic.code == "adapter_task_tools_unsupported"


def test_harness_compiler_accepts_context_for_rlm_with_exact_prompt_control() -> None:
    registry = default_kernel_registry()
    source = _recipe(registry, task_id="civil/calculation/adaptive")
    agent = source.binding("agent")
    tools = source.binding("tools")
    assert agent is not None and tools is not None
    rlm_agent = agent.model_copy(
        update={
            "capability_ref": registry.capability("aecbench.adapter.rlm").ref,
            "depends_on": ("tasks", "context"),
        }
    )
    recipe = _rebuild_recipe(
        source,
        bindings=tuple(
            rlm_agent if binding.binding_id == "agent" else binding
            for binding in source.bindings
            if binding.binding_id != tools.binding_id
        ),
    )

    compiled = compile_harness_instance(
        HarnessCompileRequest(
            request_id="compile-rlm-context",
            kernel_ref=registry.manifest.ref,
            recipe=recipe,
        ),
        registry=registry,
    )

    assert compiled.binding("context") is not None
    assert compiled.binding("agent") is not None


def test_harness_compiler_rejects_context_for_adapter_without_exact_prompt_control() -> None:
    registry = default_kernel_registry()
    source = _recipe(registry, task_id="civil/calculation/adaptive")
    agent = source.binding("agent")
    tools = source.binding("tools")
    assert agent is not None and tools is not None
    lambda_agent = agent.model_copy(
        update={
            "capability_ref": registry.capability("aecbench.adapter.lambda-rlm").ref,
            "depends_on": ("tasks", "context"),
        }
    )
    recipe = _rebuild_recipe(
        source,
        bindings=tuple(
            lambda_agent if binding.binding_id == "agent" else binding
            for binding in source.bindings
            if binding.binding_id != tools.binding_id
        ),
    )

    with pytest.raises(CompilationError) as captured:
        compile_harness_instance(
            HarnessCompileRequest(
                request_id="compile-lambda-rlm-context",
                kernel_ref=registry.manifest.ref,
                recipe=recipe,
            ),
            registry=registry,
        )

    assert captured.value.diagnostic.owner is CompilationOwner.HARNESS
    assert captured.value.diagnostic.code == "adapter_context_unsupported"


def test_harness_compiler_rejects_worker_role_in_single_agent_kernel() -> None:
    registry = default_kernel_registry()
    recipe = _recipe(registry, task_id="civil/calculation/adaptive")
    agent = recipe.binding("agent")
    assert agent is not None
    recipe = _replace_binding(
        recipe,
        agent.model_copy(update={"topology_role": HarnessTopologyRole.WORKER}),
    )

    with pytest.raises(CompilationError) as captured:
        compile_harness_instance(
            HarnessCompileRequest(
                request_id="compile-worker-role",
                kernel_ref=registry.manifest.ref,
                recipe=recipe,
            ),
            registry=registry,
        )

    assert captured.value.diagnostic.owner is CompilationOwner.HARNESS
    assert captured.value.diagnostic.code == "single_agent_role_unsupported"


def test_harness_compiler_rejects_tool_access_mode_without_runtime_mapping() -> None:
    registry = default_kernel_registry()
    recipe = _replace_configuration(
        _recipe(registry, task_id="civil/calculation/adaptive"),
        binding_id="tools",
        configuration=ToolBindingConfig(
            tool_ids=("calc",),
            access_mode=ToolAccessMode.READ_ONLY,
            max_calls=16,
        ),
    )

    with pytest.raises(CompilationError) as captured:
        compile_harness_instance(
            HarnessCompileRequest(
                request_id="compile-read-only-tools",
                kernel_ref=registry.manifest.ref,
                recipe=recipe,
            ),
            registry=registry,
        )

    assert captured.value.diagnostic.owner is CompilationOwner.HARNESS
    assert captured.value.diagnostic.code == "tool_access_mode_unsupported"


def test_harness_compiler_rejects_topology_edges_that_do_not_drive_runtime() -> None:
    registry = default_kernel_registry()
    recipe = _recipe(registry, task_id="civil/calculation/adaptive")
    importer = recipe.binding("import")
    assert importer is not None
    recipe = _replace_binding(recipe, importer.model_copy(update={"depends_on": ("compute",)}))

    with pytest.raises(CompilationError) as captured:
        compile_harness_instance(
            HarnessCompileRequest(
                request_id="compile-unwired-verifier",
                kernel_ref=registry.manifest.ref,
                recipe=recipe,
            ),
            registry=registry,
        )

    assert captured.value.diagnostic.owner is CompilationOwner.HARNESS
    assert captured.value.diagnostic.code == "unsupported_binding_topology"


def test_harness_compiler_rejects_contract_schema_without_trusted_enforcement() -> None:
    registry = default_kernel_registry()
    source = _recipe(registry, task_id="civil/calculation/adaptive")
    importer = source.binding("import")
    assert importer is not None
    contract = HarnessContractSpec(
        contract_id="opaque-output",
        kind=HarnessContractKind.OUTPUT,
        schema_ref="https://example.invalid/arbitrary-schema.json",
        enforcement=HarnessContractEnforcement.RUNTIME,
        summary="A schema for which fixed K has no trusted validator.",
    )
    recipe = _rebuild_recipe(
        source,
        contracts=(contract,),
        bindings=(
            *tuple(binding for binding in source.bindings if binding.binding_id != "import"),
            importer.model_copy(update={"contract_ids": (contract.contract_id,)}),
        ),
    )

    with pytest.raises(CompilationError) as captured:
        compile_harness_instance(
            HarnessCompileRequest(
                request_id="compile-untrusted-contract",
                kernel_ref=registry.manifest.ref,
                recipe=recipe,
            ),
            registry=registry,
        )

    assert captured.value.diagnostic.owner is CompilationOwner.HARNESS
    assert captured.value.diagnostic.code == "contract_schema_unsupported"


def test_program_compiler_pins_operations_and_topological_order() -> None:
    registry = default_kernel_registry()
    harness = _compiled_harness(registry)
    source = ExecutionProgram(
        program_id="px-adaptive",
        version="1.0.0",
        harness_ref=harness.ref,
        nodes=(
            ActionNode(node_id="run", operation_id="run_batch.v1"),
            StopNode(
                node_id="stop",
                depends_on=("run",),
                outcome=StopOutcome.SUCCEEDED,
            ),
        ),
    )

    compiled = compile_execution_program(source, harness=harness, registry=registry)
    operation = harness.program_surface.operation("run_batch.v1")

    assert operation is not None
    assert compiled.topological_order == ("run", "stop")
    assert compiled.operation_refs == (operation.ref,)
    assert compiled.source_program_ref == source.ref


def test_program_compiler_rejects_retry_for_run_batch_without_a_safe_error_taxonomy() -> None:
    registry = default_kernel_registry()
    harness = _compiled_harness(registry)
    source = ExecutionProgram(
        program_id="px-unsafe-run-batch-retry",
        version="1.0.0",
        harness_ref=harness.ref,
        nodes=(
            ActionNode(
                node_id="run",
                operation_id="run_batch.v1",
                retry=RetryPolicy(
                    max_attempts=2,
                    retry_on=("pre_dispatch_capacity_timeout",),
                ),
            ),
            StopNode(node_id="stop", depends_on=("run",), outcome=StopOutcome.SUCCEEDED),
        ),
    )

    with pytest.raises(CompilationError) as captured:
        compile_execution_program(source, harness=harness, registry=registry)

    assert captured.value.diagnostic.owner is CompilationOwner.PROGRAM
    assert captured.value.diagnostic.code == "retry_not_supported"


def test_program_compiler_rejects_a_harness_retry_taxonomy_not_attested_by_fixed_k() -> None:
    registry = default_kernel_registry()
    harness = _compiled_harness(registry)
    operation = harness.program_surface.operation("run_batch.v1")
    assert operation is not None
    tampered_operation = operation.model_copy(
        update={
            "supports_retry": True,
            "retry_safe_error_codes": ("pre_dispatch_capacity_timeout",),
        }
    )
    tampered_surface = harness.program_surface.model_copy(
        update={
            "operations": tuple(
                tampered_operation if candidate.operation_id == operation.operation_id else candidate
                for candidate in harness.program_surface.operations
            )
        }
    )
    tampered_harness = harness.model_copy(update={"program_surface": tampered_surface})
    source = ExecutionProgram(
        program_id="px-self-attested-retry",
        version="1.0.0",
        harness_ref=tampered_harness.ref,
        nodes=(
            ActionNode(node_id="run", operation_id="run_batch.v1"),
            StopNode(node_id="stop", depends_on=("run",), outcome=StopOutcome.SUCCEEDED),
        ),
    )

    with pytest.raises(CompilationError) as captured:
        compile_execution_program(source, harness=tampered_harness, registry=registry)

    assert captured.value.diagnostic.owner is CompilationOwner.HARNESS
    assert captured.value.diagnostic.code == "operation_retry_taxonomy_mismatch"


def test_program_compiler_rejects_retry_codes_outside_the_operation_safe_set() -> None:
    registry = _registry_with_retryable_run_batch(
        default_kernel_registry(),
        retry_safe_error_codes=("pre_dispatch_capacity_timeout",),
    )
    harness = _compiled_harness(registry)
    source = ExecutionProgram(
        program_id="px-unsafe-retry-code",
        version="1.0.0",
        harness_ref=harness.ref,
        nodes=(
            ActionNode(
                node_id="run",
                operation_id="run_batch.v1",
                retry=RetryPolicy(max_attempts=2, retry_on=("unknown_provider_failure",)),
            ),
            StopNode(node_id="stop", depends_on=("run",), outcome=StopOutcome.SUCCEEDED),
        ),
    )

    with pytest.raises(CompilationError) as captured:
        compile_execution_program(source, harness=harness, registry=registry)

    assert captured.value.diagnostic.owner is CompilationOwner.PROGRAM
    assert captured.value.diagnostic.code == "retry_error_code_not_safe"


def test_program_compiler_accepts_retry_codes_declared_safe_by_the_operation() -> None:
    registry = _registry_with_retryable_run_batch(
        default_kernel_registry(),
        retry_safe_error_codes=("pre_dispatch_capacity_timeout",),
    )
    harness = _compiled_harness(registry)
    source = ExecutionProgram(
        program_id="px-safe-retry-code",
        version="1.0.0",
        harness_ref=harness.ref,
        nodes=(
            ActionNode(
                node_id="run",
                operation_id="run_batch.v1",
                retry=RetryPolicy(
                    max_attempts=2,
                    retry_on=("pre_dispatch_capacity_timeout",),
                ),
            ),
            StopNode(node_id="stop", depends_on=("run",), outcome=StopOutcome.SUCCEEDED),
        ),
    )

    compiled = compile_execution_program(source, harness=harness, registry=registry)

    run_node = next(node for node in compiled.nodes if node.node_id == "run")
    assert isinstance(run_node, ActionNode)
    assert run_node.retry == RetryPolicy(
        max_attempts=2,
        retry_on=("pre_dispatch_capacity_timeout",),
    )


def test_program_compiler_attributes_unknown_operations_to_px() -> None:
    registry = default_kernel_registry()
    harness = _compiled_harness(registry)
    source = ExecutionProgram(
        program_id="px-untrusted",
        version="1.0.0",
        harness_ref=harness.ref,
        nodes=(
            ActionNode(node_id="run", operation_id="untrusted.execute.v1"),
            StopNode(node_id="stop", depends_on=("run",), outcome=StopOutcome.SUCCEEDED),
        ),
    )

    with pytest.raises(CompilationError) as captured:
        compile_execution_program(source, harness=harness, registry=registry)

    assert captured.value.diagnostic.owner is CompilationOwner.PROGRAM
    assert captured.value.diagnostic.code == "operation_outside_harness_surface"


def test_program_compiler_rejects_run_batch_argument_outside_typed_kernel_input() -> None:
    registry = default_kernel_registry()
    harness = _compiled_harness(registry)
    source = ExecutionProgram(
        program_id="px-invalid-run-input",
        version="1.0.0",
        harness_ref=harness.ref,
        nodes=(
            ActionNode(
                node_id="run",
                operation_id="run_batch.v1",
                arguments=(
                    ProgramArgument(
                        name="tasks",
                        value=LiteralValue(value=["civil/calculation/adaptive"]),
                    ),
                ),
            ),
            StopNode(node_id="stop", depends_on=("run",), outcome=StopOutcome.SUCCEEDED),
        ),
    )

    with pytest.raises(CompilationError) as captured:
        compile_execution_program(source, harness=harness, registry=registry)

    assert captured.value.diagnostic.owner is CompilationOwner.PROGRAM
    assert captured.value.diagnostic.code == "operation_argument_unsupported"


def test_program_compiler_rejects_literal_stage_receipts() -> None:
    registry = default_kernel_registry()
    task_id = "civil/calculation/adaptive"
    harness = _compiled_harness(registry, task_id=task_id)
    source = ExecutionProgram(
        program_id="px-literal-stage-receipt",
        version="1.0.0",
        harness_ref=harness.ref,
        nodes=(
            ActionNode(
                node_id="authority",
                operation_id="run_stage.v1",
                arguments=(
                    ProgramArgument(name="task_ref", value=LiteralValue(value=task_id)),
                    ProgramArgument(name="stage_id", value=LiteralValue(value="authority")),
                    ProgramArgument(
                        name="upstream_receipts",
                        value=LiteralValue(value=[{"path": "/tmp/untrusted-receipt.json"}]),
                    ),
                ),
            ),
            StopNode(node_id="stop", depends_on=("authority",), outcome=StopOutcome.SUCCEEDED),
        ),
    )

    with pytest.raises(CompilationError) as captured:
        compile_execution_program(source, harness=harness, registry=registry)

    assert captured.value.diagnostic.owner is CompilationOwner.PROGRAM
    assert captured.value.diagnostic.code == "operation_argument_unsupported"


def test_harness_compiler_rejects_recursion_without_a_fixed_k_recursive_operation() -> None:
    registry = default_kernel_registry()
    recipe_payload = _recipe(registry, task_id="civil/calculation/adaptive").model_dump(mode="python")
    recipe_payload["recursion_policy"] = HarnessRecursionPolicy(
        enabled=True,
        max_depth=2,
        max_calls=4,
        allowed_binding_ids=("agent",),
    )
    with pytest.raises(CompilationError) as captured:
        compile_harness_instance(
            HarnessCompileRequest(
                request_id="compile-recursive-harness",
                kernel_ref=registry.manifest.ref,
                recipe=HarnessRecipe.model_validate(recipe_payload),
            ),
            registry=registry,
        )

    assert captured.value.diagnostic.owner is CompilationOwner.KERNEL
    assert captured.value.diagnostic.code == "recursive_program_operation_unavailable"


def test_run_bundle_compiler_binds_real_task_package_and_infers_typed_harbor_roles(tmp_path: Path) -> None:
    registry = default_kernel_registry()
    task_id = "civil/calculation/adaptive"
    task_dir = _write_task(tmp_path / "tasks", task_id)
    (task_dir / "task-review.json").write_text(
        json.dumps(
            {
                "profile_id": "aec.task-review.civil.calculation",
                "name": "Civil calculation review",
                "task_unit": "generated-task-instance",
                "logic_profile": {"closure_gates": [], "agentic_review": {"required": True}},
                "operation_profile": {
                    "subset_axes": ["inputs"],
                    "difference_axes": ["method"],
                    "projection_axes": ["answer"],
                    "product_axes": ["discipline", "method"],
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    harness = _compiled_harness(registry, task_id=task_id)
    program = compile_execution_program(
        ExecutionProgram(
            program_id="px-adaptive",
            version="1.0.0",
            harness_ref=harness.ref,
            nodes=(
                ActionNode(node_id="run", operation_id="run_batch.v1"),
                StopNode(node_id="stop", depends_on=("run",), outcome=StopOutcome.SUCCEEDED),
            ),
        ),
        harness=harness,
        registry=registry,
    )

    first = compile_run_plan(
        run_id="bundle-adaptive",
        harness=harness,
        execution_program=program,
        registry=registry,
        tasks_root=tmp_path / "tasks",
        experiment_id="adaptive-experiment",
    )
    second = compile_run_plan(
        run_id="bundle-adaptive",
        harness=harness,
        execution_program=program,
        registry=registry,
        tasks_root=tmp_path / "tasks",
        experiment_id="adaptive-experiment",
    )

    assert first == second
    assert first.task_snapshots[0].task_id == task_id
    assert isinstance(first.review, ReviewSnapshot)
    assert first.review.tasks[0].profile_id == "aec.task-review.civil.calculation"
    assert first.run_manifest.agent.adapter == "aecbench.adapter.tool-loop"
    assert isinstance(first.harness.binding("compute").configuration, ComputeBindingConfig)
    assert isinstance(first.harness.binding("verify").configuration, VerificationBindingConfig)
    assert isinstance(first.harness.binding("import").configuration, ResultImportBindingConfig)
    assert "repetitions" not in first.model_dump(mode="json")
    assert "target_settings" not in first.model_dump(mode="json")


def test_run_bundle_compiler_accepts_an_exact_declared_stage_program(tmp_path: Path) -> None:
    registry = default_kernel_registry()
    task_id = "civil/calculation/staged"
    task_dir = _write_task(tmp_path / "tasks", task_id)
    _write_stage_world(task_dir)
    harness = _compiled_harness(registry, task_id=task_id)
    program = compile_execution_program(
        _stage_program(harness=harness, task_id=task_id),
        harness=harness,
        registry=registry,
    )

    bundle = compile_run_plan(
        run_id="bundle-staged",
        harness=harness,
        execution_program=program,
        registry=registry,
        tasks_root=tmp_path / "tasks",
        experiment_id="staged-experiment",
    )

    assert isinstance(bundle.review, ReviewSnapshot)
    graph = bundle.review.tasks[0].stage_graph
    assert graph is not None
    assert graph.topological_order == ("inventory", "authority", "decision")


def test_run_bundle_compiler_rejects_unknown_declared_stage(tmp_path: Path) -> None:
    registry = default_kernel_registry()
    task_id = "civil/calculation/staged"
    task_dir = _write_task(tmp_path / "tasks", task_id)
    _write_stage_world(task_dir)
    harness = _compiled_harness(registry, task_id=task_id)
    source = _stage_program(harness=harness, task_id=task_id)
    nodes = tuple(
        node.model_copy(
            update={
                "arguments": tuple(
                    ProgramArgument(name=argument.name, value=LiteralValue(value="not-declared"))
                    if argument.name == "stage_id"
                    else argument
                    for argument in node.arguments
                )
            }
        )
        if isinstance(node, ActionNode) and node.node_id == "decision"
        else node
        for node in source.nodes
    )
    program = compile_execution_program(
        ExecutionProgram(
            program_id=source.program_id,
            version=source.version,
            harness_ref=source.harness_ref,
            nodes=nodes,
            limits=source.limits,
        ),
        harness=harness,
        registry=registry,
    )

    with pytest.raises(CompilationError) as captured:
        compile_run_plan(
            run_id="bundle-unknown-stage",
            harness=harness,
            execution_program=program,
            registry=registry,
            tasks_root=tmp_path / "tasks",
            experiment_id="staged-experiment",
        )

    assert captured.value.diagnostic.owner is CompilationOwner.PROGRAM
    assert captured.value.diagnostic.code == "declared_stage_unknown"


def test_run_bundle_compiler_rejects_missing_declared_stage_predecessor_receipt(tmp_path: Path) -> None:
    registry = default_kernel_registry()
    task_id = "civil/calculation/staged"
    task_dir = _write_task(tmp_path / "tasks", task_id)
    _write_stage_world(task_dir)
    harness = _compiled_harness(registry, task_id=task_id)
    source = _stage_program(harness=harness, task_id=task_id)
    nodes = tuple(
        node.model_copy(
            update={
                "depends_on": ("authority",),
                "arguments": tuple(
                    ProgramArgument(
                        name="upstream_receipts",
                        value=OutputValue(ref=ProgramOutputRef(node_id="authority", output_port="stage_receipt")),
                    )
                    if argument.name == "upstream_receipts"
                    else argument
                    for argument in node.arguments
                ),
            }
        )
        if isinstance(node, ActionNode) and node.node_id == "decision"
        else node
        for node in source.nodes
        if node.node_id != "decision-inputs"
    )
    program = compile_execution_program(
        ExecutionProgram(
            program_id=source.program_id,
            version=source.version,
            harness_ref=source.harness_ref,
            nodes=nodes,
            limits=source.limits,
        ),
        harness=harness,
        registry=registry,
    )

    with pytest.raises(CompilationError) as captured:
        compile_run_plan(
            run_id="bundle-missing-predecessor",
            harness=harness,
            execution_program=program,
            registry=registry,
            tasks_root=tmp_path / "tasks",
            experiment_id="staged-experiment",
        )

    assert captured.value.diagnostic.owner is CompilationOwner.PROGRAM
    assert captured.value.diagnostic.code == "declared_stage_predecessor_mismatch"


def test_run_bundle_compiler_rejects_context_larger_than_declared_bound(tmp_path: Path) -> None:
    registry = default_kernel_registry()
    task_id = "civil/calculation/context-overflow"
    task_dir = _write_task(tmp_path / "tasks", task_id)
    (task_dir / "environment" / "system_prompt.md").write_text("x" * 4_001, encoding="utf-8")
    harness = _compiled_harness(registry, task_id=task_id)
    program = compile_execution_program(
        ExecutionProgram(
            program_id="px-context-overflow",
            version="1.0.0",
            harness_ref=harness.ref,
            nodes=(
                ActionNode(node_id="run", operation_id="run_batch.v1"),
                StopNode(node_id="stop", depends_on=("run",), outcome=StopOutcome.SUCCEEDED),
            ),
        ),
        harness=harness,
        registry=registry,
    )

    with pytest.raises(CompilationError) as captured:
        compile_run_plan(
            run_id="bundle-context-overflow",
            harness=harness,
            execution_program=program,
            registry=registry,
            tasks_root=tmp_path / "tasks",
            experiment_id="context-overflow",
        )

    assert captured.value.diagnostic.owner is CompilationOwner.HARNESS
    assert captured.value.diagnostic.code == "task_context_budget_exceeded"


def test_run_bundle_compiler_rejects_task_tool_without_a_kernel_owned_runtime(tmp_path: Path) -> None:
    registry = default_kernel_registry()
    task_id = "civil/calculation/unsupported-tool"
    _write_task(tmp_path / "tasks", task_id, tool_id="calc")
    harness = _compiled_harness(registry, task_id=task_id, tool_id="calc")
    program = compile_execution_program(
        ExecutionProgram(
            program_id="px-unsupported-tool",
            version="1.0.0",
            harness_ref=harness.ref,
            nodes=(
                ActionNode(node_id="run", operation_id="run_batch.v1"),
                StopNode(node_id="stop", depends_on=("run",), outcome=StopOutcome.SUCCEEDED),
            ),
        ),
        harness=harness,
        registry=registry,
    )

    with pytest.raises(CompilationError) as captured:
        compile_run_plan(
            run_id="bundle-unsupported-tool",
            harness=harness,
            execution_program=program,
            registry=registry,
            tasks_root=tmp_path / "tasks",
            experiment_id="unsupported-tool",
        )

    assert captured.value.diagnostic.owner is CompilationOwner.KERNEL
    assert captured.value.diagnostic.code == "task_tool_runtime_unavailable"


def _compiled_harness(
    registry: KernelRuntimeRegistry,
    *,
    task_id: str = "civil/calculation/adaptive",
    tool_id: str = "bash",
) -> CompiledHarnessInstance:
    recipe = _recipe(registry, task_id=task_id, tool_id=tool_id)
    return compile_harness_instance(
        HarnessCompileRequest(
            request_id=f"compile-{task_id.replace('/', '-')}",
            kernel_ref=registry.manifest.ref,
            recipe=recipe,
        ),
        registry=registry,
    )


def _registry_with_retryable_run_batch(
    registry: KernelRuntimeRegistry,
    *,
    retry_safe_error_codes: tuple[str, ...],
) -> KernelRuntimeRegistry:
    primitives = tuple(
        KernelRuntimePrimitive(
            spec=primitive.spec,
            runtime=ProgramOperationRuntime(
                operation=primitive.runtime.operation,
                retry_safe_error_codes=retry_safe_error_codes,
            ),
        )
        if primitive.spec.capability_id == "aecbench.operation.harbor.run-batch"
        and isinstance(primitive.runtime, ProgramOperationRuntime)
        else primitive
        for primitive in registry.primitives
    )
    return KernelRuntimeRegistry(manifest=registry.manifest, primitives=primitives)


def _recipe(
    registry: KernelRuntimeRegistry,
    *,
    task_id: str,
    tool_id: str = "bash",
) -> HarnessRecipe:
    capability = registry.capability
    return HarnessRecipe(
        recipe_id="adaptive-review",
        version="1.0.0",
        summary="Run one exact review task through the fixed Harbor kernel.",
        bindings=(
            HarnessBindingSpec(
                binding_id="tasks",
                capability_ref=capability("aecbench.tasks.registry").ref,
                topology_role=HarnessTopologyRole.SOURCE,
                configuration=TaskSourceBindingConfig(task_refs=(task_id,)),
            ),
            HarnessBindingSpec(
                binding_id="context",
                capability_ref=capability("aecbench.context.workspace-system-prompt").ref,
                depends_on=("tasks",),
                topology_role=HarnessTopologyRole.SOURCE,
                configuration=ContextBindingConfig(source_ids=("workspace.system_prompt",), max_tokens=4_000),
            ),
            HarnessBindingSpec(
                binding_id="tools",
                capability_ref=capability("aecbench.tools.task-declared").ref,
                depends_on=("tasks",),
                topology_role=HarnessTopologyRole.SERVICE,
                configuration=ToolBindingConfig(
                    tool_ids=(tool_id,),
                    access_mode=ToolAccessMode.EXECUTE,
                    max_calls=16,
                ),
            ),
            HarnessBindingSpec(
                binding_id="agent",
                capability_ref=capability("aecbench.adapter.tool-loop").ref,
                depends_on=("tasks", "context", "tools"),
                topology_role=HarnessTopologyRole.ORCHESTRATOR,
                configuration=AgentBindingConfig(
                    agent_name="adaptive-tool-loop",
                    model="test-model",
                    max_turns=8,
                    timeout_seconds=300,
                ),
            ),
            HarnessBindingSpec(
                binding_id="compute",
                capability_ref=capability("aecbench.backend.harbor.docker").ref,
                depends_on=("agent",),
                topology_role=HarnessTopologyRole.SERVICE,
                configuration=ComputeBindingConfig(max_concurrency=2),
            ),
            HarnessBindingSpec(
                binding_id="verify",
                capability_ref=capability("aecbench.verifier.task").ref,
                depends_on=("compute",),
                topology_role=HarnessTopologyRole.GATE,
                configuration=VerificationBindingConfig(enabled=True, required=True),
            ),
            HarnessBindingSpec(
                binding_id="import",
                capability_ref=capability("aecbench.results.trial-record").ref,
                depends_on=("verify",),
                topology_role=HarnessTopologyRole.SINK,
                configuration=ResultImportBindingConfig(
                    ledger_namespace="adaptive-harness",
                ),
            ),
        ),
    )


def _write_task(tasks_root: Path, task_id: str, *, tool_id: str = "bash") -> Path:
    task_dir = tasks_root / task_id
    (task_dir / "environment" / "tools").mkdir(parents=True)
    (task_dir / "tests").mkdir()
    (task_dir / "task.toml").write_text(
        f"""
[metadata]
difficulty = "easy"
visibility = "public"
tags = ["adaptive"]

[agent]
timeout_sec = 300

[[environment.tools]]
name = "{tool_id}"
source = "environment/tools/{tool_id}.sh"
description = "Run the task-owned tool."
returns_image = false
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (task_dir / "instruction.md").write_text("Solve and write /workspace/output.md.\n", encoding="utf-8")
    (task_dir / "environment" / "Dockerfile").write_text("FROM python:3.13-slim\n", encoding="utf-8")
    (task_dir / "environment" / "system_prompt.md").write_text("Use evidence.\n", encoding="utf-8")
    (task_dir / "environment" / "tools" / f"{tool_id}.sh").write_text(
        "# ABOUTME: Provides a deterministic task-owned tool fixture.\n"
        "# ABOUTME: Exists so task snapshots bind the declared executable source.\n"
        "#!/bin/sh\n",
        encoding="utf-8",
    )
    (task_dir / "tests" / "test.sh").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    (task_dir / "tests" / "test.sh").chmod(0o755)
    return task_dir


def _write_stage_world(task_dir: Path) -> None:
    (task_dir / "task-review.json").write_text(
        json.dumps(
            {
                "profile_id": "aec.task-review.civil.staged",
                "name": "Staged civil review",
                "task_unit": "generated-task-instance",
                "logic_profile": {"agentic_review": {"required": True}},
                "stages": [
                    {
                        "id": "inventory",
                        "title": "Inventory",
                        "discipline": "civil",
                        "consumes": ["document_register"],
                        "produces": ["source_inventory"],
                    },
                    {
                        "id": "authority",
                        "title": "Authority",
                        "discipline": "civil",
                        "consumes": ["source_inventory"],
                        "produces": ["provenance_ledger"],
                    },
                    {
                        "id": "decision",
                        "title": "Decision",
                        "discipline": "civil",
                        "consumes": ["provenance_ledger"],
                        "produces": ["readiness_decision"],
                    },
                ],
                "handoffs": [
                    {
                        "id": "packet_id",
                        "producer_stage": "inventory",
                        "consumer_stages": ["decision"],
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _stage_program(*, harness: CompiledHarnessInstance, task_id: str) -> ExecutionProgram:
    task_argument = ProgramArgument(name="task_ref", value=LiteralValue(value=task_id))

    def stage_argument(stage_id: str) -> ProgramArgument:
        return ProgramArgument(name="stage_id", value=LiteralValue(value=stage_id))

    return ExecutionProgram(
        program_id="px-staged",
        version="1.0.0",
        harness_ref=harness.ref,
        nodes=(
            ActionNode(
                node_id="inventory",
                operation_id="run_stage.v1",
                arguments=(task_argument, stage_argument("inventory")),
            ),
            ActionNode(
                node_id="authority",
                depends_on=("inventory",),
                operation_id="run_stage.v1",
                arguments=(
                    task_argument,
                    stage_argument("authority"),
                    ProgramArgument(
                        name="upstream_receipts",
                        value=OutputValue(ref=ProgramOutputRef(node_id="inventory", output_port="stage_receipt")),
                    ),
                ),
            ),
            JoinNode(
                node_id="decision-inputs",
                depends_on=("inventory", "authority"),
                sources=(
                    ProgramOutputRef(node_id="inventory", output_port="stage_receipt"),
                    ProgramOutputRef(node_id="authority", output_port="stage_receipt"),
                ),
            ),
            ActionNode(
                node_id="decision",
                depends_on=("decision-inputs",),
                operation_id="run_stage.v1",
                arguments=(
                    task_argument,
                    stage_argument("decision"),
                    ProgramArgument(
                        name="upstream_receipts",
                        value=OutputValue(ref=ProgramOutputRef(node_id="decision-inputs", output_port="result")),
                    ),
                ),
            ),
            JoinNode(
                node_id="all-stages",
                depends_on=("inventory", "authority", "decision"),
                sources=(
                    ProgramOutputRef(node_id="inventory", output_port="stage_receipt"),
                    ProgramOutputRef(node_id="authority", output_port="stage_receipt"),
                    ProgramOutputRef(node_id="decision", output_port="stage_receipt"),
                ),
            ),
            ActionNode(
                node_id="finalize",
                depends_on=("all-stages",),
                operation_id="finalize_task.v1",
                arguments=(
                    task_argument,
                    ProgramArgument(
                        name="stage_receipts",
                        value=OutputValue(ref=ProgramOutputRef(node_id="all-stages", output_port="result")),
                    ),
                ),
            ),
            StopNode(
                node_id="stop",
                depends_on=("finalize",),
                outcome=StopOutcome.SUCCEEDED,
                result=ProgramOutputRef(node_id="finalize", output_port="trials"),
            ),
        ),
    )


def _replace_configuration(
    recipe: HarnessRecipe,
    *,
    binding_id: str,
    configuration: ContextBindingConfig | ToolBindingConfig,
) -> HarnessRecipe:
    binding = recipe.binding(binding_id)
    assert binding is not None
    return _replace_binding(recipe, binding.model_copy(update={"configuration": configuration}))


def _replace_binding(recipe: HarnessRecipe, replacement: HarnessBindingSpec) -> HarnessRecipe:
    return _rebuild_recipe(
        recipe,
        bindings=tuple(
            replacement if binding.binding_id == replacement.binding_id else binding for binding in recipe.bindings
        ),
    )


def _rebuild_recipe(
    recipe: HarnessRecipe,
    *,
    contracts: tuple[HarnessContractSpec, ...] | None = None,
    bindings: tuple[HarnessBindingSpec, ...] | None = None,
) -> HarnessRecipe:
    payload = recipe.model_dump(mode="python")
    if contracts is not None:
        payload["contracts"] = contracts
    if bindings is not None:
        payload["bindings"] = bindings
    return HarnessRecipe.model_validate(payload)
