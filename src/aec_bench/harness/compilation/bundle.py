# ABOUTME: Compiles exact harness, program, task, and Harbor bindings into one immutable RunBundle.
# ABOUTME: Preserves task snapshot, declared-stage, verifier, and runtime-surface validation order.

from pathlib import Path

from aec_bench.contracts.execution_program import CompiledExecutionProgram
from aec_bench.contracts.harness_instance import (
    AgentBindingConfig,
    CompiledHarnessInstance,
    ComputeBindingConfig,
    ResultImportBindingConfig,
    TaskSourceBindingConfig,
    VerificationBindingConfig,
)
from aec_bench.contracts.run_bundle import HarborRunPayload, RunBundle
from aec_bench.harness.compilation.task_snapshot import resolve_task_snapshots
from aec_bench.harness.kernel_catalogue import KernelRuntimeRegistry

from .bindings import _configurations, _single_configuration
from .declared_stages import _validate_declared_stage_program
from .diagnostics import CompilationOwner, _fail
from .task_surfaces import _validate_task_bound_surfaces


def compile_run_bundle(
    *,
    bundle_id: str,
    harness: CompiledHarnessInstance,
    program: CompiledExecutionProgram,
    registry: KernelRuntimeRegistry,
    tasks_root: Path,
    experiment_id: str,
    repetitions: int = 1,
) -> RunBundle:
    """Bind exact runnable task bytes and typed Harbor roles into one immutable bundle."""
    if harness.kernel_ref != registry.manifest.ref:
        _fail(
            owner=CompilationOwner.KERNEL,
            code="kernel_reference_mismatch",
            message="compiled harness does not target the installed fixed kernel",
            subject_ids=(harness.instance_id,),
        )

    task_binding, task_configuration = _single_configuration(
        harness.bindings,
        TaskSourceBindingConfig,
        role="task source",
    )
    agent_binding, _ = _single_configuration(harness.bindings, AgentBindingConfig, role="agent")
    compute_binding, _ = _single_configuration(harness.bindings, ComputeBindingConfig, role="compute")
    import_binding, _ = _single_configuration(
        harness.bindings,
        ResultImportBindingConfig,
        role="result import",
    )
    verification_bindings = _configurations(harness.bindings, VerificationBindingConfig)
    if len(verification_bindings) > 1:
        _fail(
            owner=CompilationOwner.HARNESS,
            code="ambiguous_verifier_binding",
            message="RunBundle compilation supports at most one verifier binding",
            subject_ids=tuple(sorted(binding.binding_id for binding, _ in verification_bindings)),
        )

    _validate_task_bound_surfaces(
        harness=harness,
        registry=registry,
        tasks_root=tasks_root,
    )
    snapshots = resolve_task_snapshots(
        task_refs=task_configuration.task_refs,
        tasks_root=tasks_root,
    )
    _validate_declared_stage_program(program=program, snapshots=snapshots)
    verifier_id = verification_bindings[0][0].binding_id if verification_bindings else None
    return RunBundle(
        bundle_id=bundle_id,
        kernel_ref=registry.manifest.ref,
        harness=harness,
        program=program,
        task_snapshots=snapshots,
        harbor=HarborRunPayload(
            experiment_id=experiment_id,
            task_refs=task_configuration.task_refs,
            agent_binding_id=agent_binding.binding_id,
            compute_binding_id=compute_binding.binding_id,
            verification_binding_id=verifier_id,
            result_import_binding_id=import_binding.binding_id,
            repetitions=repetitions,
        ),
    )
