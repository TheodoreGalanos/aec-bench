# ABOUTME: Exercises causal motif learning from stage-zero and paired-repair evidence.
# ABOUTME: Proves evaluation stops before an authority-bearing reusable promotion.

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aec_bench.contracts.execution_program import (
    ActionNode,
    FanoutNode,
    ProgramLimits,
    ProgramOutputRef,
    StopNode,
    StopOutcome,
)
from aec_bench.contracts.harness_instance import (
    AgentBindingConfig,
    HarnessBindingSpec,
    HarnessRecipe,
    TaskSourceBindingConfig,
)
from aec_bench.evolution.repair_lifecycle import RepairCandidate, RepairOwner, RepairProgramTemplate
from aec_bench.harness.harbor_workflow import SynchronousHarborWorkflow
from aec_bench.meta_harness.factorial_candidates import (
    FactorialCandidateFactoryRequest,
    ProgramFactorTemplate,
)
from aec_bench.meta_harness.factorial_experiment import (
    prepare_factorial_experiment_spec as prepare_stage_zero_spec,
)
from aec_bench.meta_harness.factorial_experiment import (
    run_factorial_experiment as run_stage_zero,
)
from aec_bench.meta_harness.kernel_catalogue import KernelRuntimeRegistry
from aec_bench.meta_harness.motif_learning import (
    attest_factorial_experiment_applicability,
    capture_accepted_repair_evidence,
    derive_motif_solution_descriptor,
    learn_and_promote_motif,
)
from aec_bench.meta_harness.motif_transfer_runtime import validate_holdout_task_visibility
from aec_bench.meta_harness.motifs import (
    FactorialEvidenceReference,
    HarnessProgramMotif,
    MotifApplicabilityDescriptor,
    MotifLibrary,
    MotifPromotionPolicy,
    MotifStatus,
    MotifTemplate,
)
from aec_bench.meta_harness.repair_runtime import (
    ProgramMaxTotalAttemptsPatch,
    RepairPatchProposal,
    RepairTerminalRecord,
)
from aec_bench.meta_harness.task_snapshot import resolve_task_snapshots
from tests.meta_harness.test_repair_runtime import (
    RewardByTurnsHarborExecutor,
    _build_runtime,
    _runtime,
    _write_task,
)
from tests.meta_harness.test_stage_zero import StageZeroHarborExecutor


class RewardByProgramIdentityHarborExecutor(RewardByTurnsHarborExecutor):
    """Reward a compile-valid px mutation through its lowered program identity."""

    def __init__(self) -> None:
        super().__init__()
        self.program_hashes: list[str] = []
        self._parent_program_sha256: str | None = None

    def _reward(self, *, kwargs: dict[str, object], turns: int) -> float:
        del turns
        context = kwargs["meta_harness_context"]
        assert isinstance(context, dict)
        program_sha256 = context["program_sha256"]
        assert isinstance(program_sha256, str)
        self.program_hashes.append(program_sha256)
        if self._parent_program_sha256 is None:
            self._parent_program_sha256 = program_sha256
        return 0.2 if program_sha256 == self._parent_program_sha256 else 0.9


def test_solution_descriptor_is_derived_from_typed_harness_and_program(tmp_path: Path) -> None:
    runtime, _ = _runtime(tmp_path)
    parent = runtime.parent
    program = ProgramFactorTemplate(
        factor_id="fanout-program",
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
        limits=ProgramLimits(max_parallelism=3),
    )

    descriptor = derive_motif_solution_descriptor(parent.harness_request.recipe, program)

    assert descriptor.decomposition_pattern == "fanout"
    assert descriptor.orchestration_pattern == "bounded_parallel"
    assert descriptor.decomposition_depth == 2
    assert descriptor.maximum_parallelism == 2
    assert descriptor.tool_surface == ("enumerate_tasks.v1", "run_batch.v1")
    assert descriptor.state_mode == "ephemeral"


def test_rejected_repair_cannot_be_captured_as_learning_evidence(tmp_path: Path) -> None:
    runtime, _ = _runtime(tmp_path)
    execution = runtime.execute()
    decision = execution.result.decision
    assert decision is not None
    rejected = execution.result.model_copy(
        update={
            "status": "rejected",
            "decision": decision.model_copy(update={"accepted": False, "reasons": ("forced",)}),
        }
    )
    rejected_execution = execution.__class__(
        result=rejected,
        attempt_plan=execution.attempt_plan,
        run_artifacts=execution.run_artifacts,
        terminal=execution.terminal,
    )

    with pytest.raises(ValueError, match="accepted paired repair"):
        capture_accepted_repair_evidence(rejected_execution)


def test_transfer_requires_every_target_task_to_be_declared_holdout(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    task_id = "civil/calculation/public-transfer-target"
    _write_task(tasks_root, task_id)

    with pytest.raises(ValueError, match="transfer target tasks must be declared holdout"):
        validate_holdout_task_visibility(
            task_refs=(task_id,),
            tasks_root=tasks_root,
        )

    task_toml = tasks_root / task_id / "task.toml"
    task_toml.write_text(
        task_toml.read_text(encoding="utf-8").replace(
            'visibility = "public"',
            'visibility = "holdout"',
        ),
        encoding="utf-8",
    )
    validate_holdout_task_visibility(
        task_refs=(task_id,),
        tasks_root=tasks_root,
    )


def test_sidecar_world_contributes_one_canonical_motif_lineage(tmp_path: Path) -> None:
    runtime, _ = _runtime(tmp_path)
    task_id = runtime.request.pairing.task_ids[0]
    task_dir = runtime.tasks_root / task_id
    world_payload = {
        "world_id": "aec.world.civil.runtime-repair",
        "name": "Runtime repair world",
        "task_unit": "generated-task-instance",
        "logic_profile": {"closure_gates": [], "agentic_review": {"required": True}},
        "operation_profile": {
            "subset_axes": ["inputs"],
            "difference_axes": ["method"],
            "projection_axes": ["answer"],
            "product_axes": ["discipline", "method"],
        },
    }
    (task_dir / "world.json").write_text(json.dumps(world_payload, indent=2) + "\n", encoding="utf-8")
    snapshot = resolve_task_snapshots(task_refs=(task_id,), tasks_root=runtime.tasks_root)[0]
    assert snapshot.world is not None

    repair = capture_accepted_repair_evidence(runtime.execute())
    world_lineage = snapshot.world.world_package_sha256
    hx_template = MotifTemplate.create(kind="hx", payload={"id": "sidecar-hx"})
    px_template = MotifTemplate.create(kind="px", payload={"id": "sidecar-px"})
    factorial = FactorialEvidenceReference.create(
        analysis_sha256="4" * 64,
        subject_hx_template_sha256=hx_template.template_sha256,
        subject_px_template_sha256=px_template.template_sha256,
        world_lineage_ids=(world_lineage,),
        split="calibration",
        harness_main_effect=0.1,
        program_main_effect=0.2,
        interaction=0.3,
        joint_uplift=0.4,
        joint_incremental_uplift=0.2,
        joint_incremental_uplift_lower_bound=0.1,
        validity_rate=1.0,
        estimated_cost_usd=0.01,
    )
    motif = HarnessProgramMotif.create(
        status=MotifStatus.CANDIDATE,
        kernel_abi_sha256=runtime.registry.manifest.content_sha256,
        hx_template=hx_template,
        px_template=px_template,
        applicability=_applicability(),
        descriptor=derive_motif_solution_descriptor(
            runtime.parent.harness_request.recipe,
            _program_factor(runtime.parent.program_template),
        ),
        accepted_repair_refs=repair.references,
        factorial_evidence_refs=(factorial,),
    )

    assert snapshot.package_sha256 != world_lineage
    assert repair.references[0].world_lineage_id == world_lineage
    assert motif.supporting_world_lineage_ids == (world_lineage,)


def test_real_internal_evidence_learns_provisional_motif_without_granting_authority(
    tmp_path: Path,
) -> None:
    repair_executor = RewardByProgramIdentityHarborExecutor()
    runtime = _build_runtime(
        tmp_path / "repair",
        executor=repair_executor,
        limits=ProgramLimits(max_total_attempts=2),
        diagnosis=lambda evidence: RepairPatchProposal(
            owner=RepairOwner.PROGRAM,
            code="attempt_budget_required",
            message=f"{len(evidence.trials)} verifier outcomes require a larger px attempt budget.",
            patch=ProgramMaxTotalAttemptsPatch(max_total_attempts=3),
        ),
    )
    repair_execution = runtime.execute()
    assert repair_execution.terminal.path.exists()
    proposal = repair_execution.terminal.path.read_text(encoding="utf-8")
    assert "program_max_total_attempts" in proposal
    assert len(set(repair_executor.program_hashes)) == 2
    assert repair_execution.result.child_candidate_id is not None
    terminal_record = RepairTerminalRecord.model_validate_json(proposal)
    assert terminal_record.patch_proposal is not None
    terminal = runtime.apply_patch(terminal_record.patch_proposal)
    stage_program = _program_factor(runtime.parent.program_template)
    repaired_program = _program_factor(terminal.program_template)
    source_request = FactorialCandidateFactoryRequest(
        candidate_set_id="motif-learning.world-a",
        world_id="world-a",
        experiment_id="motif-learning-stage-zero",
        kernel_ref=runtime.registry.manifest.ref,
        task_refs=runtime.request.pairing.task_ids,
        model=_agent_model(terminal),
        harness_budget=runtime.request.pairing.budget,
        program_limits=stage_program.limits,
        seeds=(41,),
        repetitions=1,
        fixed_harness_recipe=_fixed_harness_recipe(terminal, runtime.registry),
        learned_harness_recipe=runtime.parent.harness_request.recipe,
        fixed_program=_fanout_factor(stage_program.limits),
        learned_program=stage_program,
    )
    stage_spec = prepare_stage_zero_spec(
        candidate_requests=(source_request,),
        registry=runtime.registry,
        tasks_root=runtime.tasks_root,
        policy_id="policy.motif-learning",
        randomization_seed=73,
        harness_generator_sha256="1" * 64,
        program_generator_sha256="2" * 64,
        split="discovery",
        bootstrap_replicates=8,
    )
    stage_result = run_stage_zero(
        spec=stage_spec,
        registry=runtime.registry,
        workflow=_workflow(runtime.tasks_root.parent, runtime.tasks_root),
        artifacts_root=tmp_path / "stage-artifacts",
        executor=StageZeroHarborExecutor(),
    )
    child_tasks = (
        "civil/calculation/runtime-calibration-a",
        "civil/calculation/runtime-calibration-b",
    )
    for index, task_id in enumerate(child_tasks, start=1):
        _write_task(runtime.tasks_root, task_id)
        instruction = runtime.tasks_root / task_id / "instruction.md"
        instruction.write_text(
            instruction.read_text(encoding="utf-8") + f"Calibration family {index}.\n",
            encoding="utf-8",
        )
    child_request = FactorialCandidateFactoryRequest(
        candidate_set_id="motif-learning.child-world-a",
        world_id="world-a",
        experiment_id="motif-learning-child-calibration",
        kernel_ref=runtime.registry.manifest.ref,
        task_refs=child_tasks,
        model=_agent_model(terminal),
        harness_budget=runtime.request.pairing.budget,
        program_limits=terminal.program_template.limits,
        seeds=(43,),
        repetitions=1,
        fixed_harness_recipe=_rebind_recipe_tasks(
            _fixed_harness_recipe(terminal, runtime.registry),
            task_refs=child_tasks,
        ),
        learned_harness_recipe=_rebind_recipe_tasks(
            terminal.harness_request.recipe,
            task_refs=child_tasks,
        ),
        fixed_program=_fanout_factor(terminal.program_template.limits),
        learned_program=repaired_program,
    )
    child_spec = prepare_stage_zero_spec(
        candidate_requests=(child_request,),
        registry=runtime.registry,
        tasks_root=runtime.tasks_root,
        policy_id="policy.motif-learning-child",
        randomization_seed=79,
        harness_generator_sha256="1" * 64,
        program_generator_sha256="2" * 64,
        split="calibration",
        bootstrap_replicates=8,
    )
    child_result = run_stage_zero(
        spec=child_spec,
        registry=runtime.registry,
        workflow=_workflow(runtime.tasks_root.parent, runtime.tasks_root),
        artifacts_root=tmp_path / "child-stage-artifacts",
        executor=StageZeroHarborExecutor(),
    )
    applicability = attest_factorial_experiment_applicability(
        stage_result.report,
    )
    assert applicability == stage_result.report.applicability
    policy = _policy()

    with pytest.raises(ValueError, match="child evidence must use the calibration split"):
        learn_and_promote_motif(
            source_stage_report=stage_result.report,
            child_calibration_report=stage_result.report,
            repair_execution=repair_execution,
            repaired_candidate=terminal,
            policy=policy,
            registry=runtime.registry,
            library=MotifLibrary.create(),
        )

    learned = learn_and_promote_motif(
        source_stage_report=stage_result.report,
        child_calibration_report=child_result.report,
        repair_execution=repair_execution,
        repaired_candidate=terminal,
        policy=policy,
        registry=runtime.registry,
        library=MotifLibrary.create(),
    )

    assert learned.candidate.status is MotifStatus.CANDIDATE
    assert learned.motif.status is MotifStatus.PROVISIONAL
    assert learned.report.promotion_decisions[-1].accepted is True
    assert learned.report.promotion_decisions[-1].target_status is MotifStatus.REUSABLE

    invalid_child_result = run_stage_zero(
        spec=child_spec,
        registry=runtime.registry,
        workflow=_workflow(
            runtime.tasks_root.parent,
            runtime.tasks_root,
            run_label="invalid-child",
        ),
        artifacts_root=tmp_path / "invalid-child-stage-artifacts",
        executor=StageZeroHarborExecutor(invalid_call_indices=frozenset({1})),
    )
    invalid_learning = learn_and_promote_motif(
        source_stage_report=stage_result.report,
        child_calibration_report=invalid_child_result.report,
        repair_execution=repair_execution,
        repaired_candidate=terminal,
        policy=policy,
        registry=runtime.registry,
        library=MotifLibrary.create(),
    )

    assert 0.0 < invalid_child_result.report.validity_rate < 1.0
    assert invalid_learning.motif.status is MotifStatus.PROVISIONAL
    assert invalid_learning.report.promotion_decisions[-1].accepted is False
    assert "minimum_validity_rate_not_met" in invalid_learning.report.promotion_decisions[-1].reasons


def _program_factor(template: RepairProgramTemplate) -> ProgramFactorTemplate:
    return ProgramFactorTemplate(
        factor_id=template.program_id,
        version=template.version,
        nodes=template.nodes,
        limits=template.limits,
    )


def _fixed_harness_recipe(
    candidate: RepairCandidate,
    registry: KernelRuntimeRegistry,
) -> HarnessRecipe:
    bindings = tuple(
        HarnessBindingSpec(
            binding_id=binding.binding_id,
            capability_ref=(
                registry.capability("aecbench.adapter.direct").ref
                if isinstance(binding.configuration, AgentBindingConfig)
                else binding.capability_ref
            ),
            depends_on=binding.depends_on,
            topology_role=binding.topology_role,
            contract_ids=binding.contract_ids,
            configuration=binding.configuration,
        )
        for binding in candidate.harness_request.recipe.bindings
    )
    return HarnessRecipe(
        recipe_id="fixed-direct-harness",
        version=candidate.harness_request.recipe.version,
        summary="Fixed direct-adapter baseline under the matched repaired resource budget.",
        contracts=candidate.harness_request.recipe.contracts,
        budget=candidate.harness_request.recipe.budget,
        recursion_policy=candidate.harness_request.recipe.recursion_policy,
        bindings=bindings,
    )


def _rebind_recipe_tasks(
    recipe: HarnessRecipe,
    *,
    task_refs: tuple[str, ...],
) -> HarnessRecipe:
    bindings = tuple(
        HarnessBindingSpec(
            binding_id=binding.binding_id,
            capability_ref=binding.capability_ref,
            depends_on=binding.depends_on,
            topology_role=binding.topology_role,
            contract_ids=binding.contract_ids,
            configuration=(
                TaskSourceBindingConfig(task_refs=task_refs)
                if isinstance(binding.configuration, TaskSourceBindingConfig)
                else binding.configuration
            ),
        )
        for binding in recipe.bindings
    )
    return HarnessRecipe(
        recipe_id=recipe.recipe_id,
        version=recipe.version,
        summary=recipe.summary,
        contracts=recipe.contracts,
        budget=recipe.budget,
        recursion_policy=recipe.recursion_policy,
        bindings=bindings,
    )


def _fanout_factor(limits: ProgramLimits) -> ProgramFactorTemplate:
    return ProgramFactorTemplate(
        factor_id="fixed-fanout",
        version="1.0.0",
        nodes=(
            ActionNode(node_id="enumerate", operation_id="enumerate_tasks.v1"),
            FanoutNode(
                node_id="run-each",
                depends_on=("enumerate",),
                operation_id="run_batch.v1",
                items=ProgramOutputRef(node_id="enumerate", output_port="tasks"),
                item_argument="task_ref",
                max_parallelism=1,
            ),
            StopNode(node_id="stop", depends_on=("run-each",), outcome=StopOutcome.SUCCEEDED),
        ),
        limits=limits,
    )


def _agent_model(candidate: RepairCandidate) -> str:
    agents: list[AgentBindingConfig] = [
        binding.configuration
        for binding in candidate.harness_request.recipe.bindings
        if isinstance(binding.configuration, AgentBindingConfig)
    ]
    assert len(agents) == 1
    return agents[0].model


def _applicability() -> MotifApplicabilityDescriptor:
    return MotifApplicabilityDescriptor(
        task_pattern="review_first",
        stage_pattern="evidence_then_decision",
        stage_count=3,
        fanout_characteristic="bounded",
        branching_characteristic="conditional",
        evidence_surfaces=("source_pack", "verifier_gates"),
        required_tool_surface=("run_batch.v1",),
        state_mode="ephemeral",
    )


def _policy() -> MotifPromotionPolicy:
    return MotifPromotionPolicy(
        minimum_supporting_world_lineages=1,
        minimum_objective_reward=0.8,
        minimum_validity_rate=1.0,
        minimum_joint_uplift=0.5,
        minimum_joint_incremental_uplift=0.3,
        minimum_joint_incremental_uplift_lower_bound=0.0,
        maximum_estimated_cost_usd=1.0,
        minimum_transfer_world_lineages=2,
        minimum_transfer_objective_reward=0.8,
        minimum_transfer_validity_rate=1.0,
        minimum_transfer_joint_uplift=0.5,
        minimum_transfer_joint_incremental_uplift=0.3,
        minimum_transfer_joint_incremental_uplift_lower_bound=0.0,
        maximum_transfer_estimated_cost_usd=1.0,
    )


def _workflow(
    root: Path,
    tasks_root: Path,
    *,
    run_label: str | None = None,
) -> SynchronousHarborWorkflow:
    suffix = f"-{run_label}" if run_label is not None else ""
    return SynchronousHarborWorkflow(
        project_root=root,
        repo_root=root,
        tasks_root=tasks_root,
        ledger_root=root / f"ledger{suffix}",
        jobs_root=root / f"jobs{suffix}",
    )
