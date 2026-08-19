# ABOUTME: Compiles one plain run plan from embedded harness, program, task, and run-manifest values.
# ABOUTME: Resolves task identity once and keeps provider composition and review data outside task identity.

from __future__ import annotations

from pathlib import Path

from aec_bench.contracts.evaluation_refs import EvaluationRegimeRef
from aec_bench.contracts.execution_program import CompiledExecutionProgram
from aec_bench.contracts.harness_instance import (
    AgentBindingConfig,
    CompiledHarnessInstance,
    ComputeBindingConfig,
    ResultImportBindingConfig,
    TaskSourceBindingConfig,
    VerificationBindingConfig,
)
from aec_bench.contracts.run_bundle import RunPlan
from aec_bench.contracts.task_snapshot import ArtifactTaskSnapshotRef, RepositoryTaskSnapshotRef
from aec_bench.contracts.trial_record import (
    AgentConfiguration,
    AuthorityExpectation,
    ExecutionEnvironmentRef,
    GitSourceRef,
    ProviderRoute,
    RunManifest,
    SnapshotSourceRef,
    UnresolvedSourceRef,
)
from aec_bench.harness.compilation.task_snapshot import resolve_task_material
from aec_bench.harness.kernel_catalogue import KernelRuntimeRegistry
from aec_bench.ledger.artifact_repository import ArtifactRepository

from .bindings import _configurations, _single_configuration
from .declared_stages import _validate_declared_stage_program
from .diagnostics import CompilationOwner, _fail
from .task_surfaces import _validate_task_bound_surfaces


def compile_run_plan(
    *,
    run_id: str,
    harness: CompiledHarnessInstance,
    execution_program: CompiledExecutionProgram,
    registry: KernelRuntimeRegistry,
    tasks_root: Path,
    experiment_id: str,
    artifact_repository: ArtifactRepository | None = None,
    expected_authorities: tuple[AuthorityExpectation, ...] = (),
    evaluation_regime: EvaluationRegimeRef | None = None,
) -> RunPlan:
    """Bind exact task material and domain relationships into one plain run plan."""

    if harness.kernel_ref != registry.manifest.ref:
        _fail(
            owner=CompilationOwner.KERNEL,
            code="kernel_reference_mismatch",
            message="compiled harness does not target the installed fixed kernel",
            subject_ids=(harness.instance_id,),
        )

    _, task_configuration = _single_configuration(
        harness.bindings,
        TaskSourceBindingConfig,
        role="task source",
    )
    agent_binding, agent_configuration = _single_configuration(harness.bindings, AgentBindingConfig, role="agent")
    compute_binding, _ = _single_configuration(harness.bindings, ComputeBindingConfig, role="compute")
    _single_configuration(harness.bindings, ResultImportBindingConfig, role="result import")
    verification_bindings = _configurations(harness.bindings, VerificationBindingConfig)
    if len(verification_bindings) > 1:
        _fail(
            owner=CompilationOwner.HARNESS,
            code="ambiguous_verifier_binding",
            message="run-plan compilation supports at most one verifier binding",
            subject_ids=tuple(sorted(binding.binding_id for binding, _ in verification_bindings)),
        )

    _validate_task_bound_surfaces(
        harness=harness,
        registry=registry,
        tasks_root=tasks_root,
    )
    snapshot_repository = artifact_repository or ArtifactRepository(tasks_root.parent / "artefacts" / "task-snapshots")
    material = resolve_task_material(
        task_refs=task_configuration.task_refs,
        tasks_root=tasks_root,
        artifact_repository=snapshot_repository,
    )
    _validate_declared_stage_program(program=execution_program, snapshots=material.references, review=material.review)
    provider_route = compute_binding.capability_ref.capability_id
    run_manifest = RunManifest(
        run_id=run_id,
        experiment_id=experiment_id,
        source=_run_source(material.references),
        agent=AgentConfiguration(
            adapter=agent_binding.capability_ref.capability_id,
            model=agent_configuration.model,
        ),
        execution_environment=ExecutionEnvironmentRef(
            runtime_image=f"{registry.manifest.kernel_id}:{registry.manifest.version}",
            compute_backend=provider_route,
        ),
        provider_route=ProviderRoute(
            provider=provider_route.rsplit(".", maxsplit=1)[-1],
            route=provider_route,
        ),
        expected_authorities=expected_authorities,
        evaluation_regime=evaluation_regime,
    )
    return RunPlan(
        run_manifest=run_manifest,
        task_snapshots=material.references,
        harness=harness,
        execution_program=execution_program,
        review=material.review,
    )


def _run_source(
    references: tuple[RepositoryTaskSnapshotRef | ArtifactTaskSnapshotRef, ...],
) -> GitSourceRef | SnapshotSourceRef | UnresolvedSourceRef:
    repository_revisions = {
        reference.source_revision for reference in references if isinstance(reference, RepositoryTaskSnapshotRef)
    }
    artifact_references = tuple(
        reference.artifact for reference in references if isinstance(reference, ArtifactTaskSnapshotRef)
    )
    if len(repository_revisions) == 1 and not artifact_references:
        return GitSourceRef(revision=next(iter(repository_revisions)))
    if len(artifact_references) == 1 and not repository_revisions:
        return SnapshotSourceRef(artifact=artifact_references[0])
    return UnresolvedSourceRef(reason="run source is defined by its exact task snapshot references")


__all__ = ("compile_run_plan",)
