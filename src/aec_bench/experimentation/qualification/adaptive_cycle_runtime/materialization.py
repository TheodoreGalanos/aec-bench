# ABOUTME: Materializes repaired Hx/px factors onto preregistered adaptive-cycle task surfaces.
# ABOUTME: Preserves semantic factors while rebinding only typed task inputs and resource ceilings.

from __future__ import annotations

from aec_bench.evolution.repair_lifecycle import RepairCandidate
from aec_bench.experimentation.qualification.adaptive_cycle_runtime.contracts import (
    AdaptiveHarnessProgramStageSpec,
)
from aec_bench.experimentation.qualification.adaptive_cycle_runtime.factor_bindings import (
    align_runtime_resource_budget,
    rebind_recipe_task_sources,
    task_source_refs,
)
from aec_bench.experimentation.qualification.harness_program_study.candidates import (
    HarnessProgramCandidateRequest,
    ProgramFactorTemplate,
)
from aec_bench.experimentation.qualification.motif_materialization import (
    rebind_program_task_inputs,
)


def materialize_child_harness_program_request(
    stage: AdaptiveHarnessProgramStageSpec,
    repaired_candidate: RepairCandidate,
) -> HarnessProgramCandidateRequest:
    """Materialize repaired Hx/px factors on the preregistered child task surface."""

    request = stage.instantiation
    source_task_refs = task_source_refs(repaired_candidate.harness_request.recipe)
    learned_recipe = rebind_recipe_task_sources(
        repaired_candidate.harness_request.recipe,
        task_refs=request.task_refs,
    )
    fixed_recipe = align_runtime_resource_budget(
        request.fixed_harness_recipe,
        learned_recipe,
    )
    source_program = ProgramFactorTemplate(
        factor_id=repaired_candidate.program_template.program_id,
        version=repaired_candidate.program_template.version,
        nodes=repaired_candidate.program_template.nodes,
        limits=repaired_candidate.program_template.limits,
    )
    learned_program = rebind_program_task_inputs(
        source_program,
        source_task_refs=source_task_refs,
        target_task_refs=request.task_refs,
    )
    return HarnessProgramCandidateRequest(
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
        fixed_harness_recipe=fixed_recipe,
        learned_harness_recipe=learned_recipe,
        fixed_program=request.fixed_program,
        learned_program=learned_program,
    )


def _child_harness_program_request(
    stage: AdaptiveHarnessProgramStageSpec,
    repaired_candidate: RepairCandidate,
) -> HarnessProgramCandidateRequest:
    """Retain the private helper while callers migrate to the public materializer."""

    return materialize_child_harness_program_request(stage, repaired_candidate)
