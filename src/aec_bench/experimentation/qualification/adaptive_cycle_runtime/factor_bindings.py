# ABOUTME: Owns pure adaptive-cycle task and resource rebinding across harness-program stages.
# ABOUTME: Keeps typed Hx/px surface alignment separate from cycle contracts and orchestration.

from __future__ import annotations

from aec_bench.contracts.harness_instance import (
    AgentBindingConfig,
    ComputeBindingConfig,
    ContextBindingConfig,
    HarnessBindingConfiguration,
    HarnessBindingSpec,
    HarnessSpec,
    TaskSourceBindingConfig,
    ToolBindingConfig,
)
from aec_bench.contracts.task_definition import Visibility
from aec_bench.contracts.task_snapshot import TaskSnapshotRef
from aec_bench.evolution.repair_lifecycle import RepairCandidate
from aec_bench.experimentation.governance.applicability import MotifApplicabilityAttestation
from aec_bench.experimentation.qualification.harness_program_study.candidates import (
    HarnessProgramCandidateRequest,
)
from aec_bench.experimentation.qualification.motif_materialization import (
    MotifHarnessProgramInstantiationRequest,
)


def task_source_refs(spec: HarnessSpec) -> tuple[str, ...]:
    """Return the sole typed task-source binding from a harness spec."""

    task_sources = [
        binding.configuration for binding in spec.bindings if isinstance(binding.configuration, TaskSourceBindingConfig)
    ]
    if len(task_sources) != 1:
        raise ValueError("adaptive cycle harness requires exactly one task-source binding")
    return task_sources[0].task_refs


def source_request_contains_repair_parent(
    request: HarnessProgramCandidateRequest,
    parent: RepairCandidate,
) -> bool:
    """Match the complete preregistered learned Hx/px pair to a repair parent."""

    learned_program = request.learned_program
    parent_program = parent.program_template
    return (
        request.learned_harness_spec == parent.harness_request.spec
        and learned_program.factor_id == parent_program.program_id
        and learned_program.version == parent_program.version
        and learned_program.nodes == parent_program.nodes
        and learned_program.limits == parent_program.limits
    )


def task_snapshots_for_refs(
    applicability: MotifApplicabilityAttestation,
    *,
    task_refs: tuple[str, ...],
) -> tuple[TaskSnapshotRef, ...]:
    """Select preregistered snapshots in the exact requested task order."""

    snapshots = {projection.snapshot.task_id: projection.snapshot for projection in applicability.projections}
    missing = tuple(task_ref for task_ref in task_refs if task_ref not in snapshots)
    if missing:
        raise ValueError("adaptive cycle source applicability is missing repair task snapshots: " + ", ".join(missing))
    return tuple(snapshots[task_ref] for task_ref in task_refs)


def validate_attestation_visibility(
    applicability: MotifApplicabilityAttestation,
    *,
    expected: Visibility,
    label: str,
) -> None:
    """Require complete task-review snapshots and the exact preregistered visibility."""

    missing_review = tuple(
        projection.snapshot.task_id for projection in applicability.projections if projection.review is None
    )
    if missing_review:
        raise ValueError(f"adaptive cycle {label} tasks require task-review snapshots: " + ", ".join(missing_review))
    wrong_visibility = tuple(
        projection.snapshot.task_id
        for projection in applicability.projections
        if projection.review is not None and projection.review.visibility is not expected
    )
    if wrong_visibility:
        raise ValueError(f"adaptive cycle {label} tasks must be {expected.value}: " + ", ".join(wrong_visibility))


def rebind_harness_task_sources(
    spec: HarnessSpec,
    *,
    task_refs: tuple[str, ...],
) -> HarnessSpec:
    """Rebind only the typed task-source slot while preserving learned Hx structure."""

    task_source_count = 0
    bindings: list[HarnessBindingSpec] = []
    for binding in spec.bindings:
        configuration = binding.configuration
        if isinstance(configuration, TaskSourceBindingConfig):
            task_source_count += 1
            configuration = TaskSourceBindingConfig(task_refs=task_refs)
        bindings.append(binding.model_copy(update={"configuration": configuration}))
    if task_source_count != 1:
        raise ValueError("adaptive cycle harness requires exactly one task-source binding")
    return HarnessSpec(
        summary=spec.summary,
        contracts=spec.contracts,
        budget=spec.budget,
        recursion_policy=spec.recursion_policy,
        bindings=tuple(bindings),
    )


def align_runtime_resource_budget(
    fixed: HarnessSpec,
    learned: HarnessSpec,
) -> HarnessSpec:
    """Match execution-resource ceilings without copying learned factor semantics."""

    learned_by_id = {binding.binding_id: binding for binding in learned.bindings}
    bindings = tuple(
        binding.model_copy(
            update={
                "configuration": _aligned_binding_configuration(
                    binding.configuration,
                    (learned_by_id[binding.binding_id].configuration if binding.binding_id in learned_by_id else None),
                )
            }
        )
        for binding in fixed.bindings
    )
    return HarnessSpec(
        summary=fixed.summary,
        contracts=fixed.contracts,
        budget=fixed.budget,
        recursion_policy=learned.recursion_policy,
        bindings=bindings,
    )


def align_instantiation_runtime_resource_budget(
    request: MotifHarnessProgramInstantiationRequest,
    learned: HarnessSpec,
) -> MotifHarnessProgramInstantiationRequest:
    """Apply matched Hx resource ceilings to a frozen transfer instantiation."""

    return MotifHarnessProgramInstantiationRequest(
        candidate_set_id=request.candidate_set_id,
        task_set_id=request.task_set_id,
        experiment_id=request.experiment_id,
        kernel_ref=request.kernel_ref,
        task_refs=request.task_refs,
        model=request.model,
        harness_budget=request.harness_budget,
        program_limits=request.program_limits,
        seeds=request.seeds,
        repetitions=request.repetitions,
        fixed_harness_spec=align_runtime_resource_budget(
            request.fixed_harness_spec,
            learned,
        ),
        fixed_program=request.fixed_program,
    )


def _aligned_binding_configuration(
    fixed: HarnessBindingConfiguration,
    learned: HarnessBindingConfiguration | None,
) -> HarnessBindingConfiguration:
    if isinstance(fixed, AgentBindingConfig) and isinstance(
        learned,
        AgentBindingConfig,
    ):
        return fixed.model_copy(
            update={
                "max_turns": learned.max_turns,
                "timeout_seconds": learned.timeout_seconds,
            }
        )
    if isinstance(fixed, ComputeBindingConfig) and isinstance(
        learned,
        ComputeBindingConfig,
    ):
        return fixed.model_copy(
            update={
                "max_concurrency": learned.max_concurrency,
                "timeout_override_seconds": learned.timeout_override_seconds,
            }
        )
    if isinstance(fixed, ContextBindingConfig) and isinstance(
        learned,
        ContextBindingConfig,
    ):
        return fixed.model_copy(update={"max_tokens": learned.max_tokens})
    if isinstance(fixed, ToolBindingConfig) and isinstance(
        learned,
        ToolBindingConfig,
    ):
        return fixed.model_copy(update={"max_calls": learned.max_calls})
    return fixed
