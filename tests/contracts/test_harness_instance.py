# ABOUTME: Tests typed harness recipes and compiled task-specific harness-instance contracts.
# ABOUTME: Verifies binding graphs, fixed-kernel references, program surfaces, and frozen Hx identities.

import pytest
from pydantic import ValidationError

from aec_bench.contracts.harness_instance import (
    AgentBindingConfig,
    CompiledHarnessBinding,
    CompiledHarnessInstance,
    ComputeBindingConfig,
    ContextBindingConfig,
    ContextSelectionStrategy,
    HarnessBindingSpec,
    HarnessBudget,
    HarnessCompileRequest,
    HarnessContractEnforcement,
    HarnessContractKind,
    HarnessContractSpec,
    HarnessRecipe,
    HarnessRecursionPolicy,
    HarnessTopologyRole,
    ProgramOperationScope,
    ProgramOperationSpec,
    ProgramSurface,
    ResultImportBindingConfig,
    TaskSourceBindingConfig,
    ToolAccessMode,
    ToolBindingConfig,
    VerificationBindingConfig,
    VerificationPlacement,
    VerificationStage,
)
from aec_bench.contracts.harness_kernel import (
    KernelCapabilityKind,
    KernelCapabilitySpec,
    KernelImplementationIdentity,
    KernelManifest,
    KernelPortSpec,
    KernelSourceDigest,
    canonical_content_sha256,
)


def _capability(capability_id: str, kind: KernelCapabilityKind) -> KernelCapabilitySpec:
    return KernelCapabilitySpec(
        capability_id=capability_id,
        version="1.0.0",
        kind=kind,
        summary=f"Capability {capability_id}.",
        outputs=(KernelPortSpec(name="result", schema_ref=f"aecbench://{kind.value}/v1"),),
    )


def _kernel() -> tuple[KernelManifest, dict[str, KernelCapabilitySpec]]:
    capabilities = {
        "tasks": _capability("aecbench.tasks.registry", KernelCapabilityKind.TASK_SOURCE),
        "agent": _capability("aecbench.adapter.lambda-rlm", KernelCapabilityKind.AGENT_ADAPTER),
        "compute": _capability("aecbench.backend.harbor", KernelCapabilityKind.EXECUTION_BACKEND),
        "context": _capability("aecbench.context.task-packet", KernelCapabilityKind.CONTEXT_PROVIDER),
        "tools": _capability("aecbench.tools.workspace", KernelCapabilityKind.TOOL_PROVIDER),
        "verify": _capability("aecbench.verifier.harbor", KernelCapabilityKind.VERIFIER),
        "import": _capability("aecbench.results.trial-record", KernelCapabilityKind.RESULT_IMPORTER),
        "run": _capability("aecbench.operation.run-batch", KernelCapabilityKind.PROGRAM_OPERATION),
    }
    return (
        KernelManifest(
            kernel_id="aec-bench",
            version="1.0.0",
            capabilities=tuple(capabilities.values()),
            implementation=KernelImplementationIdentity(
                sources=(KernelSourceDigest(path="kernel.py", sha256="a" * 64),),
            ),
        ),
        capabilities,
    )


def _binding_specs(capabilities: dict[str, KernelCapabilitySpec]) -> tuple[HarnessBindingSpec, ...]:
    return (
        HarnessBindingSpec(
            binding_id="tasks",
            capability_ref=capabilities["tasks"].ref,
            topology_role=HarnessTopologyRole.SOURCE,
            configuration=TaskSourceBindingConfig(
                task_refs=("civil/calculation/alpha", "civil/calculation/beta"),
            ),
        ),
        HarnessBindingSpec(
            binding_id="context",
            capability_ref=capabilities["context"].ref,
            depends_on=("tasks",),
            topology_role=HarnessTopologyRole.SOURCE,
            configuration=ContextBindingConfig(
                source_ids=("task-packet", "prior-findings"),
                selection_strategy=ContextSelectionStrategy.RETRIEVAL,
                max_tokens=8_000,
            ),
        ),
        HarnessBindingSpec(
            binding_id="tools",
            capability_ref=capabilities["tools"].ref,
            depends_on=("tasks",),
            topology_role=HarnessTopologyRole.SERVICE,
            configuration=ToolBindingConfig(
                tool_ids=("workspace.read", "workspace.write", "shell.exec"),
                access_mode=ToolAccessMode.EXECUTE,
                max_calls=64,
            ),
        ),
        HarnessBindingSpec(
            binding_id="agent",
            capability_ref=capabilities["agent"].ref,
            depends_on=("tasks", "context", "tools"),
            topology_role=HarnessTopologyRole.ORCHESTRATOR,
            configuration=AgentBindingConfig(
                agent_name="lambda-rlm",
                model="claude-sonnet-4-6",
                max_turns=12,
                timeout_seconds=600,
            ),
        ),
        HarnessBindingSpec(
            binding_id="compute",
            capability_ref=capabilities["compute"].ref,
            depends_on=("agent",),
            topology_role=HarnessTopologyRole.SERVICE,
            configuration=ComputeBindingConfig(max_concurrency=2),
        ),
        HarnessBindingSpec(
            binding_id="verify",
            capability_ref=capabilities["verify"].ref,
            depends_on=("compute",),
            topology_role=HarnessTopologyRole.GATE,
            configuration=VerificationBindingConfig(enabled=True, required=True),
        ),
        HarnessBindingSpec(
            binding_id="import",
            capability_ref=capabilities["import"].ref,
            depends_on=("verify",),
            topology_role=HarnessTopologyRole.SINK,
            configuration=ResultImportBindingConfig(ledger_namespace="adaptive-harness"),
        ),
    )


def test_harness_recipe_and_compile_request_are_typed_and_content_addressed() -> None:
    kernel, capabilities = _kernel()
    recipe = HarnessRecipe(
        recipe_id="trace-diagnosis",
        version="1.0.0",
        summary="Run trace-diagnosis tasks with a fixed Harbor harness.",
        bindings=_binding_specs(capabilities),
    )
    request = HarnessCompileRequest(
        request_id="compile-trace-diagnosis",
        kernel_ref=kernel.ref,
        recipe=recipe,
    )

    assert request.recipe.content_sha256 == recipe.content_sha256
    assert request.kernel_ref == kernel.ref
    assert len(request.content_sha256) == 64

    with pytest.raises(ValidationError, match="target_settings"):
        HarnessCompileRequest.model_validate(
            {
                **request.model_dump(mode="json", exclude={"content_sha256"}),
                "target_settings": {"manifest": {"compute": {"backend": "anything"}}},
            }
        )


def test_harness_recipe_rejects_cycles_in_the_binding_graph() -> None:
    _, capabilities = _kernel()
    first = HarnessBindingSpec(
        binding_id="first",
        capability_ref=capabilities["tasks"].ref,
        depends_on=("second",),
        topology_role=HarnessTopologyRole.SOURCE,
        configuration=TaskSourceBindingConfig(task_refs=("civil/calculation/alpha",)),
    )
    second = HarnessBindingSpec(
        binding_id="second",
        capability_ref=capabilities["agent"].ref,
        depends_on=("first",),
        topology_role=HarnessTopologyRole.WORKER,
        configuration=AgentBindingConfig(agent_name="agent", model="test-model"),
    )

    with pytest.raises(ValidationError, match="binding graph must be acyclic"):
        HarnessRecipe(
            recipe_id="cyclic",
            version="1.0.0",
            summary="A cyclic recipe.",
            bindings=(first, second),
        )


def test_binding_configuration_is_closed_and_verification_is_consistent() -> None:
    with pytest.raises(ValidationError, match="target_settings"):
        AgentBindingConfig.model_validate(
            {
                "kind": "agent",
                "agent_name": "agent",
                "model": "test-model",
                "target_settings": {"client": {"secret": "value"}},
            }
        )

    with pytest.raises(ValidationError, match="required verification cannot be disabled"):
        VerificationBindingConfig(enabled=False, required=True)


def test_agent_binding_keeps_runtime_cache_policy_out_of_historical_recipe_content() -> None:
    binding = AgentBindingConfig(agent_name="agent", model="test-model")

    assert "prompt_cache" not in binding.model_dump(mode="json")
    with pytest.raises(ValidationError, match="prompt_cache"):
        AgentBindingConfig.model_validate(
            {
                "kind": "agent",
                "agent_name": "agent",
                "model": "test-model",
                "prompt_cache": False,
            }
        )


def test_compiled_harness_instance_pins_bindings_and_exports_a_program_surface() -> None:
    kernel, capabilities = _kernel()
    recipe = HarnessRecipe(
        recipe_id="trace-diagnosis",
        version="1.0.0",
        summary="Run trace-diagnosis tasks with a fixed Harbor harness.",
        bindings=_binding_specs(capabilities),
    )
    compiled_bindings = tuple(
        CompiledHarnessBinding(
            binding_id=binding.binding_id,
            capability_ref=binding.capability_ref,
            capability_kind=capabilities[binding.binding_id].kind,
            depends_on=binding.depends_on,
            topology_role=binding.topology_role,
            configuration=binding.configuration,
        )
        for binding in recipe.bindings
    )
    surface = ProgramSurface(
        surface_id="trace-diagnosis-surface",
        operations=(
            ProgramOperationSpec(
                operation_id="run_batch.v1",
                capability_ref=capabilities["run"].ref,
                input_schema_ref="aecbench://run-batch-input/v1",
                output_schema_ref="aecbench://trial-record-set/v1",
                binding_ids=("tasks", "context", "tools", "agent", "compute", "verify", "import"),
                allowed_task_refs=("civil/calculation/alpha", "civil/calculation/beta"),
                max_parallelism=2,
                supports_retry=True,
                retry_safe_error_codes=("pre_dispatch_capacity_timeout",),
                verifier_placements=(
                    VerificationPlacement(
                        binding_id="verify",
                        stage=VerificationStage.AFTER_OPERATION,
                    ),
                ),
            ),
        ),
    )
    instance = CompiledHarnessInstance(
        instance_id="hx-trace-diagnosis",
        kernel_ref=kernel.ref,
        source_recipe_sha256=recipe.content_sha256,
        bindings=compiled_bindings,
        program_surface=surface,
    )

    assert instance.ref.content_sha256 == instance.content_sha256
    assert instance.program_surface.operations[0].operation_id == "run_batch.v1"

    with pytest.raises(ValidationError, match="outside the compiled task-source bindings"):
        CompiledHarnessInstance(
            instance_id="hx-invalid-surface",
            kernel_ref=kernel.ref,
            source_recipe_sha256=recipe.content_sha256,
            bindings=compiled_bindings,
            program_surface=ProgramSurface(
                surface_id="invalid",
                operations=(
                    ProgramOperationSpec(
                        operation_id="run_batch.v1",
                        capability_ref=capabilities["run"].ref,
                        input_schema_ref="aecbench://run-batch-input/v1",
                        output_schema_ref="aecbench://trial-record-set/v1",
                        binding_ids=("agent", "compute"),
                        allowed_task_refs=("civil/calculation/not-allowed",),
                    ),
                ),
            ),
        )


def test_program_operation_retry_support_requires_an_explicit_safe_error_taxonomy() -> None:
    _, capabilities = _kernel()
    common = {
        "operation_id": "run_batch.v1",
        "capability_ref": capabilities["run"].ref,
        "input_schema_ref": "aecbench://run-batch-input/v1",
        "output_schema_ref": "aecbench://trial-record-set/v1",
        "binding_ids": ("tasks",),
    }

    with pytest.raises(ValidationError, match="retry support requires explicit safe error codes"):
        ProgramOperationSpec(**common, supports_retry=True)

    with pytest.raises(ValidationError, match="retry-safe error codes require retry support"):
        ProgramOperationSpec(
            **common,
            retry_safe_error_codes=("pre_dispatch_capacity_timeout",),
        )

    with pytest.raises(ValidationError, match="retry-safe error codes must be unique"):
        ProgramOperationSpec(
            **common,
            supports_retry=True,
            retry_safe_error_codes=(
                "pre_dispatch_capacity_timeout",
                "pre_dispatch_capacity_timeout",
            ),
        )

    with pytest.raises(ValidationError, match="wildcard retry-safe error codes are not permitted"):
        ProgramOperationSpec(
            **common,
            supports_retry=True,
            retry_safe_error_codes=("*",),
        )

    with pytest.raises(ValidationError, match="prohibited retry-safe error codes"):
        ProgramOperationSpec(
            **common,
            supports_retry=True,
            retry_safe_error_codes=("harbor_workflow_failed",),
        )


def test_public_program_operation_preserves_legacy_canonical_payload() -> None:
    _, capabilities = _kernel()
    legacy_payload = {
        "operation_id": "run_batch.v1",
        "capability_ref": capabilities["run"].ref.model_dump(mode="json"),
        "input_schema_ref": "aecbench://run-batch-input/v1",
        "output_schema_ref": "aecbench://trial-record-set/v1",
        "binding_ids": ("tasks",),
        "contract_ids": (),
        "allowed_task_refs": (),
        "max_parallelism": 1,
        "supports_retry": False,
        "retry_safe_error_codes": (),
        "supports_recursion": False,
        "verifier_placements": (),
    }
    legacy_sha256 = canonical_content_sha256(legacy_payload)

    operation = ProgramOperationSpec.model_validate({**legacy_payload, "content_sha256": legacy_sha256})

    assert operation.required_compilation_scope is ProgramOperationScope.PUBLIC
    assert operation.content_sha256 == legacy_sha256
    assert "required_compilation_scope" not in operation.model_dump(mode="json")

    internal = ProgramOperationSpec.model_validate(
        {
            **legacy_payload,
            "required_compilation_scope": ProgramOperationScope.PROPOSAL_SESSION_INTERNAL,
        }
    )
    assert (
        internal.model_dump(mode="json")["required_compilation_scope"]
        == ProgramOperationScope.PROPOSAL_SESSION_INTERNAL
    )
    assert internal.content_sha256 != legacy_sha256


def test_harness_recipe_captures_budgets_contracts_topology_and_recursion() -> None:
    _, capabilities = _kernel()
    output_contract = HarnessContractSpec(
        contract_id="verified-trial-record",
        kind=HarnessContractKind.OUTPUT,
        schema_ref="aecbench://trial-record/v1",
        enforcement=HarnessContractEnforcement.RUNTIME,
        summary="Every imported result is a valid, verified trial record.",
    )
    bindings = list(_binding_specs(capabilities))
    agent_index = next(index for index, binding in enumerate(bindings) if binding.binding_id == "agent")
    bindings[agent_index] = bindings[agent_index].model_copy(update={"contract_ids": (output_contract.contract_id,)})
    recipe = HarnessRecipe(
        recipe_id="full-surface",
        version="1.0.0",
        summary="Represent the complete minimum adaptive harness surface.",
        contracts=(output_contract,),
        budget=HarnessBudget(
            max_parallelism=8,
            max_total_attempts=64,
            max_agent_turns=32,
            max_tool_calls=128,
            max_context_tokens=16_000,
            max_runtime_seconds=3_600,
            max_tokens=250_000,
            max_cost_usd=25.0,
        ),
        recursion_policy=HarnessRecursionPolicy(
            enabled=True,
            max_depth=4,
            max_calls=32,
            allowed_binding_ids=("agent",),
        ),
        bindings=tuple(bindings),
    )

    context_binding = recipe.binding("context")
    tool_binding = recipe.binding("tools")
    agent_binding = recipe.binding("agent")
    assert context_binding is not None
    assert tool_binding is not None
    assert agent_binding is not None
    assert context_binding.configuration.kind.value == "context"
    assert tool_binding.configuration.kind.value == "tool"
    assert agent_binding.topology_role is HarnessTopologyRole.ORCHESTRATOR
    assert recipe.contracts == (output_contract,)
    assert recipe.recursion_policy.allowed_binding_ids == ("agent",)


def test_compiled_harness_rejects_unknown_operation_provenance_and_verifier_placement() -> None:
    kernel, capabilities = _kernel()
    recipe = HarnessRecipe(
        recipe_id="invalid-operation-provenance",
        version="1.0.0",
        summary="Exercise compiled operation provenance checks.",
        bindings=_binding_specs(capabilities),
    )
    compiled_bindings = tuple(
        CompiledHarnessBinding(
            binding_id=binding.binding_id,
            capability_ref=binding.capability_ref,
            capability_kind=capabilities[binding.binding_id].kind,
            depends_on=binding.depends_on,
            topology_role=binding.topology_role,
            configuration=binding.configuration,
        )
        for binding in recipe.bindings
    )

    with pytest.raises(ValidationError, match="unknown binding ids: missing"):
        CompiledHarnessInstance(
            instance_id="hx-invalid-operation-provenance",
            kernel_ref=kernel.ref,
            source_recipe_sha256=recipe.content_sha256,
            bindings=compiled_bindings,
            program_surface=ProgramSurface(
                surface_id="invalid-provenance",
                operations=(
                    ProgramOperationSpec(
                        operation_id="run_batch.v1",
                        capability_ref=capabilities["run"].ref,
                        input_schema_ref="aecbench://run-batch-input/v1",
                        output_schema_ref="aecbench://trial-record-set/v1",
                        binding_ids=("agent", "missing"),
                        verifier_placements=(
                            VerificationPlacement(
                                binding_id="agent",
                                stage=VerificationStage.AFTER_OPERATION,
                            ),
                        ),
                    ),
                ),
            ),
        )

    with pytest.raises(ValidationError, match="must reference a verification binding"):
        CompiledHarnessInstance(
            instance_id="hx-invalid-verifier-placement",
            kernel_ref=kernel.ref,
            source_recipe_sha256=recipe.content_sha256,
            bindings=compiled_bindings,
            program_surface=ProgramSurface(
                surface_id="invalid-verifier-placement",
                operations=(
                    ProgramOperationSpec(
                        operation_id="run_batch.v1",
                        capability_ref=capabilities["run"].ref,
                        input_schema_ref="aecbench://run-batch-input/v1",
                        output_schema_ref="aecbench://trial-record-set/v1",
                        binding_ids=("agent",),
                        verifier_placements=(
                            VerificationPlacement(
                                binding_id="agent",
                                stage=VerificationStage.AFTER_OPERATION,
                            ),
                        ),
                    ),
                ),
            ),
        )

    with pytest.raises(ValidationError, match="allowed task refs are not backed by named task-source bindings"):
        CompiledHarnessInstance(
            instance_id="hx-unwired-operation-tasks",
            kernel_ref=kernel.ref,
            source_recipe_sha256=recipe.content_sha256,
            bindings=compiled_bindings,
            program_surface=ProgramSurface(
                surface_id="unwired-operation-tasks",
                operations=(
                    ProgramOperationSpec(
                        operation_id="run_batch.v1",
                        capability_ref=capabilities["run"].ref,
                        input_schema_ref="aecbench://run-batch-input/v1",
                        output_schema_ref="aecbench://trial-record-set/v1",
                        binding_ids=("agent",),
                        allowed_task_refs=("civil/calculation/alpha",),
                    ),
                ),
            ),
        )


def test_harness_recipe_rejects_binding_configuration_outside_its_budget() -> None:
    _, capabilities = _kernel()

    with pytest.raises(ValidationError, match="context tokens exceed harness budget"):
        HarnessRecipe(
            recipe_id="over-budget-context",
            version="1.0.0",
            summary="Reject context bindings larger than the Hx resource envelope.",
            budget=HarnessBudget(max_context_tokens=1_000),
            bindings=_binding_specs(capabilities),
        )


def test_usage_budgets_are_optional_when_the_runtime_cannot_measure_them() -> None:
    budget = HarnessBudget(max_tokens=None, max_cost_usd=None)

    assert budget.max_tokens is None
    assert budget.max_cost_usd is None
