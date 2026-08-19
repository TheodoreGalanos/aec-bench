# ABOUTME: Lowers an immutable RunPlan into exact, trusted Harbor runtime inputs.
# ABOUTME: Revalidates task bytes and resolves every execution-bearing Hx binding through fixed K.

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Never, TypeVar, cast

from aec_bench.contracts.execution_program import ActionNode, FanoutNode
from aec_bench.contracts.experiment_manifest import AgentConfig, ComputeConfig, ExperimentManifest, TaskSelector
from aec_bench.contracts.harness_instance import (
    AgentBindingConfig,
    CompiledHarnessBinding,
    ComputeBindingConfig,
    ContextBindingConfig,
    HarnessBindingConfiguration,
    ProgramOperationSpec,
    ResultImportBindingConfig,
    ToolBindingConfig,
    VerificationBindingConfig,
)
from aec_bench.contracts.harness_kernel import KernelCapabilityRef
from aec_bench.contracts.output_completion import OutputCompletionContract
from aec_bench.contracts.run_bundle import RunPlan
from aec_bench.contracts.stage_execution import KernelInstructionOverride
from aec_bench.contracts.task_definition import TaskDefinition, ToolSpec
from aec_bench.contracts.task_snapshot import ArtifactTaskSnapshotRef, TaskSnapshotRef, task_snapshot_id
from aec_bench.contracts.trajectory import MetaHarnessTrajectoryContext
from aec_bench.harness.compilation import CompilationDiagnostic, CompilationOwner
from aec_bench.harness.compilation.task_snapshot import TaskSnapshotError, build_task_snapshot
from aec_bench.harness.harbor_dispatch import build_harbor_job_config
from aec_bench.harness.kernel_catalogue import (
    AgentAdapterRuntime,
    ContextProviderRuntime,
    HarborBackendRuntime,
    KernelRuntimePrimitive,
    KernelRuntimeRegistry,
    KernelRuntimeRegistryError,
    ProgramOperationRuntime,
    ResultImporterRuntime,
    ToolProviderRuntime,
    VerifierRuntime,
)
from aec_bench.tasks.loader import load_task_definition
from aec_bench.tasks.registry import TaskRegistry
from aec_bench.tasks.snapshot import build_task_snapshot_archive

ConfigurationT = TypeVar("ConfigurationT", bound=HarnessBindingConfiguration)
HarborOperation = Literal[
    "harbor_run_batch",
    "harbor_run_stage",
    "harbor_finalize_task",
]
_HARBOR_OUTPUT_COMPLETION_PATH = "/workspace/output.md"


class HarborLoweringError(ValueError):
    """Raised when a RunPlan cannot be faithfully lowered to the installed runtime."""

    def __init__(self, diagnostic: CompilationDiagnostic) -> None:
        self.diagnostic = diagnostic
        super().__init__(diagnostic.message)


@dataclass(frozen=True)
class LoweredHarborRun:
    """Exact Harbor manifest, task objects, and result-import policy for one px invocation."""

    manifest: ExperimentManifest
    tasks: tuple[TaskDefinition, ...]
    ledger_namespace: str
    required_artifact_kinds: tuple[str, ...]
    agent_turn_capacity: int
    tool_call_capacity: int
    context_token_capacity: int
    meta_harness_context: MetaHarnessTrajectoryContext
    operation_runtime: HarborOperation
    effective_instruction_by_task_id: dict[str, str]

    def harbor_job_config(self, *, jobs_dir: Path | str = "jobs") -> dict[str, object]:
        """Build and validate the concrete Harbor-facing job payload from these exact tasks."""
        return cast(
            dict[str, object],
            build_harbor_job_config(
                manifest=self.manifest,
                tasks=list(self.tasks),
                jobs_dir=jobs_dir,
            ),
        )


def lower_run_bundle(
    bundle: RunPlan,
    *,
    registry: KernelRuntimeRegistry,
    tasks_root: Path,
    program_node_id: str,
    attempt: int = 1,
    fanout_index: int | None = None,
    run_id: str | None = None,
    task_refs: tuple[str, ...] | None = None,
    repair_iteration: int | None = None,
    execution_seed: int | None = None,
    motif_ids: tuple[str, ...] = (),
    remaining_runtime_seconds: int | None = None,
    instruction_override: KernelInstructionOverride | None = None,
    repetitions: int = 1,
) -> LoweredHarborRun:
    """Resolve one px operation invocation without accepting agent-selected runtime hooks."""
    _validate_kernel(bundle=bundle, registry=registry)
    operation, operation_runtime = _resolve_program_operation(
        bundle=bundle,
        registry=registry,
        program_node_id=program_node_id,
    )
    harbor_operation = _harbor_operation(
        operation_runtime,
        operation_id=operation.operation_id,
    )
    operation_binding_ids = operation.binding_ids
    selected_bindings = {
        binding.binding_id: binding
        for binding in bundle.harness.bindings
        if binding.binding_id in operation_binding_ids
    }
    if set(selected_bindings) != set(operation_binding_ids):
        missing = tuple(sorted(set(operation_binding_ids) - set(selected_bindings)))
        _fail(
            owner=CompilationOwner.HARNESS,
            code="operation_binding_missing",
            message="invoked Hx operation references bindings absent from the bundled harness",
            subject_ids=missing,
        )

    selected_task_refs = task_refs or tuple(task_snapshot_id(snapshot) for snapshot in bundle.task_snapshots)
    if not selected_task_refs or len(selected_task_refs) != len(set(selected_task_refs)):
        _fail(
            owner=CompilationOwner.PROGRAM,
            code="invalid_runtime_task_selection",
            message="runtime task selection must be non-empty and unique",
            subject_ids=tuple(sorted(set(selected_task_refs))),
        )
    outside_operation = tuple(sorted(set(selected_task_refs) - set(operation.allowed_task_refs)))
    if outside_operation:
        _fail(
            owner=CompilationOwner.PROGRAM,
            code="runtime_task_outside_operation_surface",
            message="runtime task selection is outside the invoked Hx operation surface",
            subject_ids=outside_operation,
        )
    tasks = _resolve_exact_tasks(
        bundle=bundle,
        tasks_root=tasks_root,
        task_refs=selected_task_refs,
    )
    agent_binding, agent_configuration, agent_primitive = _selected_binding(
        bundle=bundle,
        registry=registry,
        selected_bindings=selected_bindings,
        binding_id=_binding_id(bundle, AgentBindingConfig),
        configuration_type=AgentBindingConfig,
        runtime_type=AgentAdapterRuntime,
        role="agent",
    )
    _, compute_configuration, compute_primitive = _selected_binding(
        bundle=bundle,
        registry=registry,
        selected_bindings=selected_bindings,
        binding_id=_binding_id(bundle, ComputeBindingConfig),
        configuration_type=ComputeBindingConfig,
        runtime_type=HarborBackendRuntime,
        role="compute",
    )
    if harbor_operation == "harbor_run_stage":
        ledger_namespace = "__intermediate-stage-no-import__"
        required_artifact_kinds: tuple[str, ...] = ()
        verification_enabled = False
    else:
        _, import_configuration, _ = _selected_binding(
            bundle=bundle,
            registry=registry,
            selected_bindings=selected_bindings,
            binding_id=_binding_id(bundle, ResultImportBindingConfig),
            configuration_type=ResultImportBindingConfig,
            runtime_type=ResultImporterRuntime,
            role="result import",
        )
        ledger_namespace = import_configuration.ledger_namespace
        required_artifact_kinds = import_configuration.required_artifacts
        verification_enabled = _verification_enabled(
            bundle=bundle,
            registry=registry,
            selected_bindings=selected_bindings,
        )
    adapter_runtime = cast(AgentAdapterRuntime, agent_primitive.runtime)
    parameters = _agent_parameters(
        bundle=bundle,
        registry=registry,
        tasks=tasks,
        tasks_root=tasks_root,
        selected_bindings=selected_bindings,
        program_node_id=program_node_id,
        attempt=attempt,
        repair_iteration=repair_iteration,
        execution_seed=execution_seed,
        motif_ids=motif_ids,
        agent_configuration=agent_configuration,
        agent_runtime=adapter_runtime,
        runtime_seconds=_runtime_seconds(
            bundle=bundle,
            remaining_runtime_seconds=remaining_runtime_seconds,
        ),
    )
    effective_instruction_by_task_id = _effective_instructions(
        tasks=tasks,
        operation_runtime=harbor_operation,
        instruction_override=instruction_override,
        repetitions=repetitions,
    )
    if instruction_override is not None:
        parameters["kernel_instruction_override"] = instruction_override.model_dump(mode="json")
    meta_harness_context = MetaHarnessTrajectoryContext.model_validate(parameters["meta_harness_context"])
    backend_runtime = cast(HarborBackendRuntime, compute_primitive.runtime)
    fanout_suffix = "" if fanout_index is None else f"-f{fanout_index}"
    run_suffix = "" if run_id is None else f"-{_safe_id(run_id)}"
    experiment_id = (
        f"{bundle.run_manifest.experiment_id}{run_suffix}-{_safe_id(program_node_id)}-a{attempt}{fanout_suffix}"
    )
    manifest = ExperimentManifest(
        experiment_id=experiment_id,
        name=f"Adaptive harness {bundle.run_manifest.run_id} / {program_node_id} / attempt {attempt}",
        description=(
            f"Run plan {bundle.run_manifest.run_id}; "
            f"Hx {bundle.harness.instance_id}; "
            f"px {bundle.execution_program.program_id}@{bundle.execution_program.version}."
        ),
        tasks=TaskSelector(include_patterns=list(selected_task_refs)),
        agents=[
            AgentConfig(
                name=agent_configuration.agent_name,
                adapter=adapter_runtime.adapter_kind,
                model=agent_configuration.model,
                parameters=parameters,
            )
        ],
        compute=ComputeConfig(
            backend=backend_runtime.backend,
            resource_limits={
                "n_concurrent_trials": (1 if fanout_index is not None else compute_configuration.max_concurrency)
            },
            timeout_override=min(
                compute_configuration.timeout_override_seconds or bundle.harness.budget.max_runtime_seconds,
                _runtime_seconds(
                    bundle=bundle,
                    remaining_runtime_seconds=remaining_runtime_seconds,
                ),
            ),
        ),
        repetitions=repetitions,
        disable_verification=not verification_enabled,
    )
    del agent_binding
    trial_slots = len(tasks) * repetitions
    return LoweredHarborRun(
        manifest=manifest,
        tasks=tasks,
        ledger_namespace=ledger_namespace,
        required_artifact_kinds=required_artifact_kinds,
        agent_turn_capacity=agent_configuration.max_turns * trial_slots,
        tool_call_capacity=_nonnegative_integer_parameter(parameters, "max_tool_calls") * trial_slots,
        context_token_capacity=_nonnegative_integer_parameter(parameters, "context_budget_tokens") * trial_slots,
        meta_harness_context=meta_harness_context,
        operation_runtime=harbor_operation,
        effective_instruction_by_task_id=effective_instruction_by_task_id,
    )


def _effective_instructions(
    *,
    tasks: tuple[TaskDefinition, ...],
    operation_runtime: str,
    instruction_override: KernelInstructionOverride | None,
    repetitions: int,
) -> dict[str, str]:
    if operation_runtime == "harbor_run_batch":
        if instruction_override is not None:
            _fail(
                owner=CompilationOwner.RUNTIME,
                code="batch_instruction_override_forbidden",
                message="the fixed-K batch operation does not accept instruction overrides",
            )
        return {task.task_id: task.instruction for task in tasks}

    expected_mode = "declared_stage" if operation_runtime == "harbor_run_stage" else "task_finalization"
    if len(tasks) != 1 or repetitions != 1:
        _fail(
            owner=CompilationOwner.PROGRAM,
            code="staged_operation_requires_single_task_repetition",
            message="declared-stage operations require exactly one task and one repetition",
            subject_ids=tuple(task.task_id for task in tasks),
        )
    if instruction_override is None or instruction_override.mode != expected_mode:
        _fail(
            owner=CompilationOwner.RUNTIME,
            code="staged_instruction_override_missing",
            message=f"{operation_runtime} requires a kernel-owned {expected_mode} instruction override",
            subject_ids=(tasks[0].task_id,),
        )
    task = tasks[0]
    if instruction_override.task_id != task.task_id:
        _fail(
            owner=CompilationOwner.PROGRAM,
            code="staged_instruction_task_mismatch",
            message="kernel instruction override task does not match the selected exact task",
            subject_ids=(instruction_override.task_id, task.task_id),
        )
    observed_instruction_sha256 = hashlib.sha256(task.instruction.encode("utf-8")).hexdigest()
    if instruction_override.original_instruction_sha256 != observed_instruction_sha256:
        _fail(
            owner=CompilationOwner.WORLD,
            code="staged_instruction_source_mismatch",
            message="kernel instruction override does not bind the selected task instruction bytes",
            subject_ids=(task.task_id,),
        )
    return {task.task_id: instruction_override.effective_instruction}


def _validate_kernel(*, bundle: RunPlan, registry: KernelRuntimeRegistry) -> None:
    if bundle.harness.kernel_ref != registry.manifest.ref:
        _fail(
            owner=CompilationOwner.KERNEL,
            code="kernel_reference_mismatch",
            message="RunPlan does not target the installed fixed kernel",
            subject_ids=(bundle.harness.kernel_ref.kernel_id,),
        )


def _resolve_program_operation(
    *,
    bundle: RunPlan,
    registry: KernelRuntimeRegistry,
    program_node_id: str,
) -> tuple[ProgramOperationSpec, ProgramOperationRuntime]:
    node = next(
        (candidate for candidate in bundle.execution_program.nodes if candidate.node_id == program_node_id),
        None,
    )
    if not isinstance(node, ActionNode | FanoutNode):
        _fail(
            owner=CompilationOwner.PROGRAM,
            code="program_node_not_runnable_operation",
            message="Harbor lowering requires an action or fanout px node",
            subject_ids=(program_node_id,),
        )
    operation = bundle.harness.program_surface.operation(node.operation_id)
    if operation is None:
        _fail(
            owner=CompilationOwner.PROGRAM,
            code="operation_outside_harness_surface",
            message="px node operation is not exported by the bundled Hx surface",
            subject_ids=(node.operation_id, program_node_id),
        )
    primitive = _resolve_primitive(
        registry=registry,
        reference=operation.capability_ref,
        owner=CompilationOwner.KERNEL,
        code="operation_capability_not_installed",
        subject_ids=(operation.operation_id,),
    )
    if not isinstance(primitive.runtime, ProgramOperationRuntime):
        _fail(
            owner=CompilationOwner.RUNTIME,
            code="unsupported_program_operation_runtime",
            message="installed operation does not resolve to a trusted program runtime",
            subject_ids=(operation.operation_id,),
        )
    return operation, primitive.runtime


def _harbor_operation(
    runtime: ProgramOperationRuntime,
    *,
    operation_id: str,
) -> HarborOperation:
    if runtime.operation == "harbor_run_batch":
        return "harbor_run_batch"
    if runtime.operation == "harbor_run_stage":
        return "harbor_run_stage"
    if runtime.operation == "harbor_finalize_task":
        return "harbor_finalize_task"
    _fail(
        owner=CompilationOwner.RUNTIME,
        code="operation_is_not_harbor_runnable",
        message="Harbor lowering accepts only fixed-K Harbor execution operations",
        subject_ids=(operation_id,),
    )


def _resolve_exact_tasks(
    *,
    bundle: RunPlan,
    tasks_root: Path,
    task_refs: tuple[str, ...],
) -> tuple[TaskDefinition, ...]:
    expected_by_id = {snapshot.task_id: snapshot for snapshot in bundle.task_snapshots}
    missing_snapshots = tuple(sorted(set(task_refs) - set(expected_by_id)))
    if missing_snapshots:
        _fail(
            owner=CompilationOwner.WORLD,
            code="runtime_task_snapshot_missing",
            message="runtime task selection is absent from the immutable RunPlan snapshots",
            subject_ids=missing_snapshots,
        )
    expected_snapshots = tuple(expected_by_id[task_ref] for task_ref in task_refs)
    mismatched = tuple(
        snapshot.task_id
        for snapshot in expected_snapshots
        if not _task_material_matches(snapshot=snapshot, tasks_root=tasks_root)
    )
    if mismatched:
        _fail(
            owner=CompilationOwner.WORLD,
            code="task_snapshot_mismatch",
            message="task package bytes changed after RunPlan compilation",
            subject_ids=mismatched,
        )
    task_registry = TaskRegistry(tasks_root=Path(tasks_root))
    task_registry.reload()
    by_id = {task.task_id: task for task in task_registry.all()}
    if task_registry.load_errors:
        relevant_errors = [
            str(path)
            for path, _ in task_registry.load_errors
            if any((Path(tasks_root) / task_ref) in path.parents for task_ref in task_refs)
        ]
        if relevant_errors:
            _fail(
                owner=CompilationOwner.WORLD,
                code="task_registry_load_error",
                message="exact task package failed registry validation",
                subject_ids=tuple(sorted(relevant_errors)),
            )
    return tuple(by_id[task_ref] for task_ref in task_refs)


def _task_material_matches(*, snapshot: TaskSnapshotRef, tasks_root: Path) -> bool:
    task_dir = Path(tasks_root) / snapshot.task_id
    try:
        if isinstance(snapshot, ArtifactTaskSnapshotRef):
            payload = build_task_snapshot_archive(task_dir)
            return (
                len(payload) == snapshot.artifact.size_bytes
                and hashlib.sha256(payload).hexdigest() == snapshot.artifact.sha256
            )
        task = load_task_definition(task_dir, Path(tasks_root))
        return build_task_snapshot(task=task, tasks_root=tasks_root) == snapshot
    except (OSError, TaskSnapshotError, ValueError):
        return False


def _binding_id(bundle: RunPlan, configuration_type: type[HarnessBindingConfiguration]) -> str:
    matching = tuple(
        binding.binding_id
        for binding in bundle.harness.bindings
        if isinstance(binding.configuration, configuration_type)
    )
    if len(matching) != 1:
        _fail(
            owner=CompilationOwner.HARNESS,
            code="run_plan_binding_role_invalid",
            message=f"run plan requires exactly one {configuration_type.__name__} binding",
            subject_ids=matching,
        )
    return matching[0]


def _optional_binding_id(bundle: RunPlan, configuration_type: type[HarnessBindingConfiguration]) -> str | None:
    matching = tuple(
        binding.binding_id
        for binding in bundle.harness.bindings
        if isinstance(binding.configuration, configuration_type)
    )
    if len(matching) > 1:
        _fail(
            owner=CompilationOwner.HARNESS,
            code="run_plan_binding_role_invalid",
            message=f"run plan supports at most one {configuration_type.__name__} binding",
            subject_ids=matching,
        )
    return matching[0] if matching else None


def _selected_binding(
    *,
    bundle: RunPlan,
    registry: KernelRuntimeRegistry,
    selected_bindings: dict[str, CompiledHarnessBinding],
    binding_id: str,
    configuration_type: type[ConfigurationT],
    runtime_type: type,
    role: str,
) -> tuple[CompiledHarnessBinding, ConfigurationT, KernelRuntimePrimitive]:
    binding = selected_bindings.get(binding_id)
    if binding is None or not isinstance(binding.configuration, configuration_type):
        _fail(
            owner=CompilationOwner.HARNESS,
            code=f"selected_{role.replace(' ', '_')}_binding_invalid",
            message=f"selected {role} binding is absent or has the wrong configuration role",
            subject_ids=(binding_id,),
        )
    primitive = _resolve_primitive(
        registry=registry,
        reference=binding.capability_ref,
        owner=CompilationOwner.KERNEL,
        code=f"selected_{role.replace(' ', '_')}_capability_not_installed",
        subject_ids=(binding_id,),
    )
    if not isinstance(primitive.runtime, runtime_type):
        _fail(
            owner=CompilationOwner.RUNTIME,
            code=f"selected_{role.replace(' ', '_')}_runtime_invalid",
            message=f"selected {role} capability resolves to the wrong trusted runtime kind",
            subject_ids=(binding_id,),
        )
    return binding, binding.configuration, primitive


def _verification_enabled(
    *,
    bundle: RunPlan,
    registry: KernelRuntimeRegistry,
    selected_bindings: dict[str, CompiledHarnessBinding],
) -> bool:
    binding_id = _optional_binding_id(bundle, VerificationBindingConfig)
    if binding_id is None:
        return False
    _, configuration, _ = _selected_binding(
        bundle=bundle,
        registry=registry,
        selected_bindings=selected_bindings,
        binding_id=binding_id,
        configuration_type=VerificationBindingConfig,
        runtime_type=VerifierRuntime,
        role="verification",
    )
    return configuration.enabled


def _agent_parameters(
    *,
    bundle: RunPlan,
    registry: KernelRuntimeRegistry,
    tasks: tuple[TaskDefinition, ...],
    tasks_root: Path,
    selected_bindings: dict[str, CompiledHarnessBinding],
    program_node_id: str,
    attempt: int,
    repair_iteration: int | None,
    execution_seed: int | None,
    motif_ids: tuple[str, ...],
    agent_configuration: AgentBindingConfig,
    agent_runtime: AgentAdapterRuntime,
    runtime_seconds: int,
) -> dict[str, object]:
    parameters: dict[str, object] = {
        "max_turns": agent_configuration.max_turns,
        "prompt_cache": agent_runtime.prompt_cache,
        "timeout_sec": min(agent_configuration.timeout_seconds, runtime_seconds),
    }
    if execution_seed is not None:
        parameters["execution_seed"] = execution_seed
    if agent_runtime.completion_policy in {
        "task_output_contract",
        "task_output_commit",
    }:
        parameters["output_completion_contract"] = _task_output_completion_contract(
            tasks=tasks,
            tasks_root=tasks_root,
        ).model_dump(mode="json")
    if agent_runtime.completion_policy == "task_output_commit":
        parameters["output_completion_commit"] = True
    parameters.update(
        _context_parameters(
            registry=registry,
            tasks=tasks,
            tasks_root=tasks_root,
            selected_bindings=selected_bindings,
        )
    )
    parameters.update(
        _tool_parameters(
            registry=registry,
            tasks=tasks,
            selected_bindings=selected_bindings,
        )
    )
    lineage = MetaHarnessTrajectoryContext(
        kernel_ref=bundle.harness.kernel_ref,
        harness_ref=bundle.harness.ref,
        program_ref=bundle.execution_program.ref,
        plan_run_id=bundle.run_manifest.run_id,
        program_node_id=program_node_id,
        binding_ids=tuple(sorted(selected_bindings)),
        repair_iteration=repair_iteration,
        execution_seed=execution_seed,
        attempt=attempt,
        motif_ids=tuple(sorted(motif_ids)),
    )
    parameters["meta_harness_context"] = lineage.model_dump(mode="json")
    return parameters


def _context_parameters(
    *,
    registry: KernelRuntimeRegistry,
    tasks: tuple[TaskDefinition, ...],
    tasks_root: Path,
    selected_bindings: dict[str, CompiledHarnessBinding],
) -> dict[str, object]:
    context_bindings = [
        binding for binding in selected_bindings.values() if isinstance(binding.configuration, ContextBindingConfig)
    ]
    if len(context_bindings) > 1:
        _fail(
            owner=CompilationOwner.HARNESS,
            code="ambiguous_context_binding",
            message="initial Harbor lowering supports at most one context binding",
            subject_ids=tuple(sorted(binding.binding_id for binding in context_bindings)),
        )
    if not context_bindings:
        return {}
    binding = context_bindings[0]
    primitive = _resolve_primitive(
        registry=registry,
        reference=binding.capability_ref,
        owner=CompilationOwner.KERNEL,
        code="context_capability_not_installed",
        subject_ids=(binding.binding_id,),
    )
    if not isinstance(primitive.runtime, ContextProviderRuntime):
        _fail(
            owner=CompilationOwner.RUNTIME,
            code="context_runtime_invalid",
            message="context binding does not resolve to the trusted context provider",
            subject_ids=(binding.binding_id,),
        )
    context_configuration = cast(ContextBindingConfig, binding.configuration)
    prompt_values = tuple(
        (Path(tasks_root) / task.task_id / "environment" / "system_prompt.md").read_text(encoding="utf-8")
        for task in tasks
    )
    if len(set(prompt_values)) != 1:
        _fail(
            owner=CompilationOwner.HARNESS,
            code="non_uniform_task_context",
            message="one Harbor agent configuration cannot materialize different task system prompts",
            subject_ids=tuple(task.task_id for task in tasks),
        )
    context_bytes = len(prompt_values[0].encode("utf-8"))
    if context_bytes > context_configuration.max_tokens:
        _fail(
            owner=CompilationOwner.HARNESS,
            code="task_context_budget_exceeded",
            message=(
                f"runtime context requires {context_bytes} UTF-8 bytes, exceeding "
                f"conservative token bound {context_configuration.max_tokens}"
            ),
            subject_ids=(binding.binding_id,),
        )
    return {
        "system_prompt": prompt_values[0],
        "context_budget_tokens": context_configuration.max_tokens,
        "context_utf8_bytes": context_bytes,
        "context_accounting": "utf8_bytes_upper_bound",
    }


def _tool_parameters(
    *,
    registry: KernelRuntimeRegistry,
    tasks: tuple[TaskDefinition, ...],
    selected_bindings: dict[str, CompiledHarnessBinding],
) -> dict[str, object]:
    tool_bindings = [
        binding for binding in selected_bindings.values() if isinstance(binding.configuration, ToolBindingConfig)
    ]
    if len(tool_bindings) > 1:
        _fail(
            owner=CompilationOwner.HARNESS,
            code="ambiguous_tool_binding",
            message="initial Harbor lowering supports at most one tool binding",
            subject_ids=tuple(sorted(binding.binding_id for binding in tool_bindings)),
        )
    if not tool_bindings:
        return {}
    binding = tool_bindings[0]
    primitive = _resolve_primitive(
        registry=registry,
        reference=binding.capability_ref,
        owner=CompilationOwner.KERNEL,
        code="tool_capability_not_installed",
        subject_ids=(binding.binding_id,),
    )
    if not isinstance(primitive.runtime, ToolProviderRuntime):
        _fail(
            owner=CompilationOwner.RUNTIME,
            code="tool_runtime_invalid",
            message="tool binding does not resolve to the trusted task tool provider",
            subject_ids=(binding.binding_id,),
        )
    tool_configuration = cast(ToolBindingConfig, binding.configuration)
    task_tool_payloads = tuple(_selected_task_tools(task, tool_configuration) for task in tasks)
    first_tool_payload = task_tool_payloads[0]
    if any(payload != first_tool_payload for payload in task_tool_payloads[1:]):
        _fail(
            owner=CompilationOwner.HARNESS,
            code="non_uniform_task_tools",
            message="one Harbor agent configuration cannot materialize different task tool surfaces",
            subject_ids=tuple(task.task_id for task in tasks),
        )
    return {
        "tools": [tool.model_dump(mode="json") for tool in first_tool_payload],
        "tool_access_mode": tool_configuration.access_mode.value,
        "max_tool_calls": tool_configuration.max_calls,
    }


def _task_output_completion_contract(
    *,
    tasks: tuple[TaskDefinition, ...],
    tasks_root: Path,
) -> OutputCompletionContract:
    contracts: list[tuple[str, OutputCompletionContract]] = []
    for task in tasks:
        path = Path(tasks_root) / task.task_id / "environment" / "output_contract.json"
        if not path.is_file():
            _fail(
                owner=CompilationOwner.WORLD,
                code="output_completion_contract_missing",
                message="output-contract completion requires a task-owned environment/output_contract.json",
                subject_ids=(task.task_id,),
            )
        try:
            contract = OutputCompletionContract.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            _fail(
                owner=CompilationOwner.WORLD,
                code="output_completion_contract_invalid",
                message=f"task-owned output completion contract is invalid: {error}",
                subject_ids=(task.task_id,),
            )
        if contract.output_path != task.verifier.expected_output_path:
            _fail(
                owner=CompilationOwner.WORLD,
                code="output_completion_contract_path_mismatch",
                message=(
                    "task-owned output completion contract path must match the task verifier's expected output path"
                ),
                subject_ids=(task.task_id,),
            )
        if contract.output_path != _HARBOR_OUTPUT_COMPLETION_PATH:
            _fail(
                owner=CompilationOwner.RUNTIME,
                code="unsupported_output_completion_path",
                message=(
                    "output-contract completion requires the Harbor entrypoint and artifact collector path "
                    f"{_HARBOR_OUTPUT_COMPLETION_PATH}"
                ),
                subject_ids=(task.task_id,),
            )
        contracts.append((task.task_id, contract))

    first = contracts[0][1]
    non_uniform = tuple(
        task_id for task_id, contract in contracts if contract.model_dump(mode="json") != first.model_dump(mode="json")
    )
    if non_uniform:
        _fail(
            owner=CompilationOwner.WORLD,
            code="non_uniform_output_completion_contract",
            message="one Harbor agent configuration cannot materialize different output completion contracts",
            subject_ids=tuple(sorted(task_id for task_id, _ in contracts)),
        )
    return first


def _runtime_seconds(*, bundle: RunPlan, remaining_runtime_seconds: int | None) -> int:
    if remaining_runtime_seconds is None:
        return bundle.harness.budget.max_runtime_seconds
    if remaining_runtime_seconds < 1:
        _fail(
            owner=CompilationOwner.HARNESS,
            code="harness_runtime_budget_exceeded",
            message="remaining Hx runtime allowance must be positive",
            subject_ids=(bundle.harness.instance_id,),
        )
    return min(bundle.harness.budget.max_runtime_seconds, remaining_runtime_seconds)


def _selected_task_tools(task: TaskDefinition, configuration: ToolBindingConfig) -> tuple[ToolSpec, ...]:
    by_name = {tool.name: tool for tool in task.environment.tools}
    missing = tuple(sorted(set(configuration.tool_ids) - set(by_name)))
    if missing:
        _fail(
            owner=CompilationOwner.HARNESS,
            code="tool_not_declared_by_task",
            message=f"task {task.task_id!r} does not declare every selected tool",
            subject_ids=tuple(sorted((task.task_id, *missing))),
        )
    return tuple(by_name[tool_id] for tool_id in configuration.tool_ids)


def _resolve_primitive(
    *,
    registry: KernelRuntimeRegistry,
    reference: KernelCapabilityRef,
    owner: CompilationOwner,
    code: str,
    subject_ids: tuple[str, ...],
) -> KernelRuntimePrimitive:
    try:
        return registry.resolve(reference)
    except KernelRuntimeRegistryError as error:
        _fail(
            owner=owner,
            code=code,
            message=str(error),
            subject_ids=subject_ids,
        )


def _safe_id(value: str) -> str:
    return "".join(character if character.isalnum() or character in "-." else "-" for character in value)


def _nonnegative_integer_parameter(parameters: dict[str, object], name: str) -> int:
    value = parameters.get(name, 0)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        _fail(
            owner=CompilationOwner.RUNTIME,
            code="invalid_agent_capacity_parameter",
            message=f"trusted agent parameter {name!r} must be a non-negative integer",
            subject_ids=(name,),
        )
    return value


def _fail(
    *,
    owner: CompilationOwner,
    code: str,
    message: str,
    subject_ids: tuple[str, ...] = (),
) -> Never:
    raise HarborLoweringError(
        CompilationDiagnostic(
            owner=owner,
            code=code,
            message=message,
            subject_ids=tuple(sorted(set(subject_ids))),
        )
    )
