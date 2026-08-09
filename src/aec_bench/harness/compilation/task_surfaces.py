# ABOUTME: Validates task-bound tool and context surfaces before RunBundle materialization.
# ABOUTME: Preserves binding-order attribution across world, harness, kernel, and runtime failures.

from pathlib import Path

from aec_bench.contracts.harness_instance import (
    CompiledHarnessBinding,
    CompiledHarnessInstance,
    ContextBindingConfig,
    TaskSourceBindingConfig,
    ToolBindingConfig,
)
from aec_bench.contracts.task_definition import TaskDefinition
from aec_bench.harness.kernel_catalogue import (
    KernelRuntimeRegistry,
    ToolProviderRuntime,
)
from aec_bench.tasks.registry import TaskRegistry

from .bindings import _single_configuration
from .diagnostics import CompilationOwner, _fail


def _validate_task_bound_surfaces(
    *,
    harness: CompiledHarnessInstance,
    registry: KernelRuntimeRegistry,
    tasks_root: Path,
) -> None:
    _, task_configuration = _single_configuration(
        harness.bindings,
        TaskSourceBindingConfig,
        role="task source",
    )
    task_registry = TaskRegistry(tasks_root=Path(tasks_root))
    task_registry.reload()
    tasks = {task.task_id: task for task in task_registry.all()}
    for binding in harness.bindings:
        configuration = binding.configuration
        if isinstance(configuration, ToolBindingConfig):
            _validate_task_tool_surface(
                binding=binding,
                configuration=configuration,
                task_refs=task_configuration.task_refs,
                tasks=tasks,
                registry=registry,
            )
        elif isinstance(configuration, ContextBindingConfig):
            _validate_task_context_surface(
                binding=binding,
                configuration=configuration,
                task_refs=task_configuration.task_refs,
                tasks_root=tasks_root,
            )


def _validate_task_tool_surface(
    *,
    binding: CompiledHarnessBinding,
    configuration: ToolBindingConfig,
    task_refs: tuple[str, ...],
    tasks: dict[str, TaskDefinition],
    registry: KernelRuntimeRegistry,
) -> None:
    primitive = registry.resolve(binding.capability_ref)
    runtime = primitive.runtime
    if not isinstance(runtime, ToolProviderRuntime):
        _fail(
            owner=CompilationOwner.RUNTIME,
            code="tool_runtime_invalid",
            message="task-tool binding does not resolve to a kernel-owned tool runtime",
            subject_ids=(binding.binding_id,),
        )
    unsupported = tuple(sorted(set(configuration.tool_ids) - set(runtime.supported_tool_ids)))
    if unsupported:
        _fail(
            owner=CompilationOwner.KERNEL,
            code="task_tool_runtime_unavailable",
            message="fixed K has no native runtime for selected task tools: " + ", ".join(unsupported),
            subject_ids=unsupported,
        )
    for task_id in task_refs:
        task = tasks.get(task_id)
        if task is None:
            continue
        available = {tool.name for tool in task.environment.tools}
        missing = sorted(set(configuration.tool_ids) - available)
        if missing:
            _fail(
                owner=CompilationOwner.HARNESS,
                code="tool_not_declared_by_task",
                message=f"task {task_id!r} does not declare bound tools: {', '.join(missing)}",
                subject_ids=tuple(sorted((task_id, *missing))),
            )


def _validate_task_context_surface(
    *,
    binding: CompiledHarnessBinding,
    configuration: ContextBindingConfig,
    task_refs: tuple[str, ...],
    tasks_root: Path,
) -> None:
    unsupported_sources = sorted(set(configuration.source_ids) - {"workspace.system_prompt"})
    if unsupported_sources:
        _fail(
            owner=CompilationOwner.HARNESS,
            code="context_source_not_supported",
            message="fixed kernel does not support context sources: " + ", ".join(unsupported_sources),
            subject_ids=tuple(unsupported_sources),
        )
    for task_id in task_refs:
        prompt = Path(tasks_root) / task_id / "environment" / "system_prompt.md"
        if "workspace.system_prompt" in configuration.source_ids and not prompt.is_file():
            _fail(
                owner=CompilationOwner.WORLD,
                code="task_context_missing",
                message=f"task context source is missing: {task_id}/environment/system_prompt.md",
                subject_ids=(task_id,),
            )
        if "workspace.system_prompt" in configuration.source_ids and prompt.is_file():
            context_bytes = len(prompt.read_bytes())
            if context_bytes > configuration.max_tokens:
                _fail(
                    owner=CompilationOwner.HARNESS,
                    code="task_context_budget_exceeded",
                    message=(
                        f"task {task_id!r} context requires {context_bytes} UTF-8 bytes, "
                        f"exceeding conservative token bound {configuration.max_tokens}"
                    ),
                    subject_ids=(binding.binding_id, task_id),
                )
