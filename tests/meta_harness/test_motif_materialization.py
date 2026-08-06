# ABOUTME: Tests safe materialization of selected motif templates into target-specific Hx and px factors.
# ABOUTME: Proves frozen motif decisions become genuine four-cell candidates without carrying source-world identity.

from __future__ import annotations

from pathlib import Path

import pytest

from aec_bench.contracts.execution_program import (
    ActionNode,
    FanoutNode,
    LiteralValue,
    ProgramArgument,
    ProgramLimits,
    ProgramOutputRef,
    StopNode,
    StopOutcome,
)
from aec_bench.contracts.harness_instance import (
    AgentBindingConfig,
    ComputeBindingConfig,
    HarnessBindingSpec,
    HarnessBudget,
    HarnessRecipe,
    HarnessTopologyRole,
    ResultImportBindingConfig,
    TaskSourceBindingConfig,
    VerificationBindingConfig,
)
from aec_bench.meta_harness.factorial_candidates import (
    ProgramFactorTemplate,
    materialize_factorial_candidates,
)
from aec_bench.meta_harness.factorial_plan import FactorialCell
from aec_bench.meta_harness.kernel_catalogue import KernelRuntimeRegistry, default_kernel_registry
from aec_bench.meta_harness.motif_materialization import (
    MotifFactorialInstantiationRequest,
    encode_harness_motif_template,
    encode_program_motif_template,
    instantiate_selected_motif_factors,
    rebind_program_task_inputs,
)
from aec_bench.meta_harness.motifs import (
    HarnessProgramMotif,
    MotifApplicabilityDescriptor,
    MotifLibrary,
    MotifSelectionOutcome,
    MotifSelectionRequest,
    MotifStatus,
    MotifStructuralDescriptor,
    MotifTemplate,
    select_motif,
)
from tests.support.adaptive_harness import write_adaptive_task


def test_selected_motif_materializes_target_specific_factors_and_real_candidates(tmp_path: Path) -> None:
    registry = default_kernel_registry()
    source_budget = HarnessBudget(max_parallelism=2)
    target_budget = HarnessBudget(max_parallelism=3)
    source_limits = ProgramLimits(max_parallelism=2)
    target_limits = ProgramLimits(max_parallelism=3)
    source_recipe = _recipe(
        registry,
        recipe_id="source-hx",
        task_refs=("source/family/world",),
        model="source-model",
        adapter_capability="aecbench.adapter.rlm",
        budget=source_budget,
    )
    source_program = _fanout_program("source-px", source_limits)
    motif = _motif(source_recipe, source_program)
    library = MotifLibrary.create((motif,))
    selection_request = _selection_request(library)
    selection = select_motif(library, selection_request)
    target_task = "civil/calculation/target-world"
    tasks_root = tmp_path / "tasks"
    write_adaptive_task(tasks_root, task_id=target_task)

    instantiated = instantiate_selected_motif_factors(
        library=library,
        selection_request=selection_request,
        selection_decision=selection,
        request=MotifFactorialInstantiationRequest(
            candidate_set_id="motif.target-world",
            world_id="world.target-world",
            experiment_id="experiment.target-world",
            kernel_ref=registry.manifest.ref,
            task_refs=(target_task,),
            model="claude-sonnet-4-6",
            harness_budget=target_budget,
            program_limits=target_limits,
            seeds=(17, 29),
            repetitions=2,
            fixed_harness_recipe=_recipe(
                registry,
                recipe_id="target-h0",
                task_refs=(target_task,),
                model="claude-sonnet-4-6",
                adapter_capability="aecbench.adapter.tool-loop",
                budget=target_budget,
            ),
            fixed_program=_monolithic_program("target-p0", target_limits),
        ),
    )
    materialized = materialize_factorial_candidates(
        instantiated.factorial_request,
        registry=registry,
        tasks_root=tasks_root,
    )

    assert selection.outcome is MotifSelectionOutcome.SELECTED
    assert instantiated.selected_motif_sha256 == motif.motif_sha256
    assert instantiated.selection_request_sha256 == selection_request.request_sha256
    assert instantiated.selection_decision_sha256 == selection.decision_sha256
    assert instantiated.source_harness_template_sha256 == motif.hx_template.template_sha256
    assert instantiated.source_program_template_sha256 == motif.px_template.template_sha256
    assert instantiated.factorial_request.learned_harness_recipe.budget == target_budget
    assert instantiated.factorial_request.learned_program.limits == target_limits
    learned_tasks = _configuration(
        instantiated.factorial_request.learned_harness_recipe,
        TaskSourceBindingConfig,
    )
    learned_agent = _configuration(
        instantiated.factorial_request.learned_harness_recipe,
        AgentBindingConfig,
    )
    assert learned_tasks.task_refs == (target_task,)
    assert learned_agent.model == "claude-sonnet-4-6"
    assert "source/family/world" not in str(instantiated.model_dump(mode="json"))
    assert tuple(candidate.cell for candidate in materialized.candidates) == tuple(FactorialCell)
    assert all(candidate.bundle.harbor.task_refs == (target_task,) for candidate in materialized.candidates)


def test_motif_materialization_rejects_no_selection_and_untyped_template_payload() -> None:
    registry = default_kernel_registry()
    budget = HarnessBudget()
    limits = ProgramLimits()
    fixed_recipe = _recipe(
        registry,
        recipe_id="fixed",
        task_refs=("target/world",),
        model="claude-sonnet-4-6",
        adapter_capability="aecbench.adapter.tool-loop",
        budget=budget,
    )
    request = MotifFactorialInstantiationRequest(
        candidate_set_id="candidate.target",
        world_id="world.target",
        experiment_id="experiment.target",
        kernel_ref=registry.manifest.ref,
        task_refs=("target/world",),
        model="claude-sonnet-4-6",
        harness_budget=budget,
        program_limits=limits,
        seeds=(17,),
        repetitions=1,
        fixed_harness_recipe=fixed_recipe,
        fixed_program=_monolithic_program("fixed-p0", limits),
    )

    empty_library = MotifLibrary.create()
    no_match_request = _selection_request(empty_library)
    no_match = select_motif(empty_library, no_match_request)
    with pytest.raises(ValueError, match="did not select a motif"):
        instantiate_selected_motif_factors(
            library=empty_library,
            selection_request=no_match_request,
            selection_decision=no_match,
            request=request,
        )

    malformed = HarnessProgramMotif.create(
        status=MotifStatus.REUSABLE,
        kernel_abi_sha256=registry.manifest.content_sha256,
        hx_template=MotifTemplate.create(kind="hx", payload={"entrypoint": "arbitrary.import"}),
        px_template=encode_program_motif_template(_fanout_program("selected-px", limits)),
        applicability=_applicability(),
        descriptor=_descriptor(),
    )
    malformed_library = MotifLibrary.create((malformed,))
    malformed_request = _selection_request(malformed_library)
    malformed_decision = select_motif(malformed_library, malformed_request)
    with pytest.raises(ValueError, match="typed HarnessRecipe payload"):
        instantiate_selected_motif_factors(
            library=malformed_library,
            selection_request=malformed_request,
            selection_decision=malformed_decision,
            request=request,
        )


def test_program_task_rebinding_changes_only_declared_operation_input_slots() -> None:
    source_task = "source/family/world"
    target_task = "target/family/world"
    source = ProgramFactorTemplate(
        factor_id="literal-source-px",
        version="1.0.0",
        nodes=(
            ActionNode(
                node_id="run",
                operation_id="run_batch.v1",
                arguments=(
                    ProgramArgument(
                        name="task_ref",
                        value=LiteralValue(value=source_task),
                    ),
                    ProgramArgument(
                        name="diagnostic_label",
                        value=LiteralValue(value=source_task),
                    ),
                ),
            ),
            StopNode(node_id="stop", depends_on=("run",), outcome=StopOutcome.SUCCEEDED),
        ),
    )

    rebound = rebind_program_task_inputs(
        source,
        source_task_refs=(source_task,),
        target_task_refs=(target_task,),
    )

    run = rebound.nodes[0]
    assert isinstance(run, ActionNode)
    assert run.arguments == (
        ProgramArgument(name="task_ref", value=LiteralValue(value=target_task)),
        ProgramArgument(name="diagnostic_label", value=LiteralValue(value=source_task)),
    )
    assert source.nodes[0] != run


def test_program_task_rebinding_rejects_ambiguous_or_foreign_task_coordinates() -> None:
    source = ProgramFactorTemplate(
        factor_id="literal-source-px",
        version="1.0.0",
        nodes=(
            ActionNode(
                node_id="run",
                operation_id="run_batch.v1",
                arguments=(ProgramArgument(name="task_ref", value=LiteralValue(value="foreign/world")),),
            ),
            StopNode(node_id="stop", depends_on=("run",), outcome=StopOutcome.SUCCEEDED),
        ),
    )

    with pytest.raises(ValueError, match="outside the declared source task slots"):
        rebind_program_task_inputs(
            source,
            source_task_refs=("source/world",),
            target_task_refs=("target/world",),
        )
    with pytest.raises(ValueError, match="one-to-one task cardinality"):
        rebind_program_task_inputs(
            source,
            source_task_refs=("source/world",),
            target_task_refs=("target/a", "target/b"),
        )


def _motif(recipe: HarnessRecipe, program: ProgramFactorTemplate) -> HarnessProgramMotif:
    registry = default_kernel_registry()
    return HarnessProgramMotif.create(
        status=MotifStatus.REUSABLE,
        kernel_abi_sha256=registry.manifest.content_sha256,
        hx_template=encode_harness_motif_template(recipe),
        px_template=encode_program_motif_template(program),
        applicability=_applicability(),
        descriptor=_descriptor(),
    )


def _selection_request(library: MotifLibrary) -> MotifSelectionRequest:
    return MotifSelectionRequest.create(
        archive_sha256=library.archive_sha256,
        archive_frozen=True,
        kernel_abi_sha256=default_kernel_registry().manifest.content_sha256,
        applicability=_applicability(),
        selection_split="discovery",
    )


def _applicability() -> MotifApplicabilityDescriptor:
    return MotifApplicabilityDescriptor(
        task_pattern="task_batch",
        stage_pattern="independent_tasks",
        stage_count=1,
        fanout_characteristic="bounded",
        branching_characteristic="none",
        evidence_surfaces=("trial_record",),
        required_tool_surface=("harbor.run-batch",),
        state_mode="ephemeral",
    )


def _descriptor() -> MotifStructuralDescriptor:
    return MotifStructuralDescriptor(
        decomposition_pattern="task_fanout",
        orchestration_pattern="bounded_parallel",
        decomposition_depth=1,
        maximum_parallelism=2,
        tool_surface=("harbor.run-batch",),
        state_mode="ephemeral",
    )


def _monolithic_program(factor_id: str, limits: ProgramLimits) -> ProgramFactorTemplate:
    return ProgramFactorTemplate(
        factor_id=factor_id,
        version="1.0.0",
        nodes=(
            ActionNode(node_id="run", operation_id="run_batch.v1"),
            StopNode(node_id="stop", depends_on=("run",), outcome=StopOutcome.SUCCEEDED),
        ),
        limits=limits,
    )


def _fanout_program(factor_id: str, limits: ProgramLimits) -> ProgramFactorTemplate:
    return ProgramFactorTemplate(
        factor_id=factor_id,
        version="1.0.0",
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
            StopNode(node_id="stop", depends_on=("run-each",), outcome=StopOutcome.SUCCEEDED),
        ),
        limits=limits,
    )


def _recipe(
    registry: KernelRuntimeRegistry,
    *,
    recipe_id: str,
    task_refs: tuple[str, ...],
    model: str,
    adapter_capability: str,
    budget: HarnessBudget,
) -> HarnessRecipe:
    capability = registry.capability
    return HarnessRecipe(
        recipe_id=recipe_id,
        version="1.0.0",
        summary="One transferable fixed-K harness motif.",
        budget=budget,
        bindings=(
            HarnessBindingSpec(
                binding_id="tasks",
                capability_ref=capability("aecbench.tasks.registry").ref,
                topology_role=HarnessTopologyRole.SOURCE,
                configuration=TaskSourceBindingConfig(task_refs=task_refs),
            ),
            HarnessBindingSpec(
                binding_id="agent",
                capability_ref=capability(adapter_capability).ref,
                depends_on=("tasks",),
                topology_role=HarnessTopologyRole.ORCHESTRATOR,
                configuration=AgentBindingConfig(
                    agent_name=f"{recipe_id}-agent",
                    model=model,
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
                configuration=ResultImportBindingConfig(ledger_namespace="motif-materialization"),
            ),
        ),
    )


def _configuration[ConfigurationT](recipe: HarnessRecipe, kind: type[ConfigurationT]) -> ConfigurationT:
    matches = [binding.configuration for binding in recipe.bindings if isinstance(binding.configuration, kind)]
    assert len(matches) == 1
    return matches[0]
