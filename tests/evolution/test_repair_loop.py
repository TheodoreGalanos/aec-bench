# ABOUTME: Tests the closed verifier-guided repair loop over typed Hx and px compiler contracts.
# ABOUTME: Proves exact paired reruns, owner-scoped mutation, lineage, and post-mutation verification.

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from pydantic import ValidationError

from aec_bench.contracts.execution_program import (
    ActionNode,
    ProgramLimits,
    StopNode,
    StopOutcome,
)
from aec_bench.contracts.harness_instance import (
    AgentBindingConfig,
    ComputeBindingConfig,
    ContextBindingConfig,
    HarnessBindingSpec,
    HarnessBudget,
    HarnessCompileRequest,
    HarnessSpec,
    HarnessTopologyRole,
    ResultImportBindingConfig,
    TaskSourceBindingConfig,
    ToolAccessMode,
    ToolBindingConfig,
    VerificationBindingConfig,
)
from aec_bench.contracts.task_snapshot import TaskSnapshotRef
from aec_bench.evolution.paired_repair import (
    RepairAcceptancePolicy,
    RepairMutationScope,
    RepairTrialOutcome,
)
from aec_bench.evolution.repair_lifecycle import (
    CompiledRepairCandidate,
    RepairCandidate,
    RepairDiagnosis,
    RepairExecutionObservation,
    RepairExecutionStatus,
    RepairFailureDomain,
    RepairLoopDependencies,
    RepairLoopError,
    RepairLoopRequest,
    RepairLoopResult,
    RepairLoopStatus,
    RepairOwner,
    RepairPairingSpec,
    RepairPatchRequest,
    RepairProgramTemplate,
    RepairRewardCoverage,
    RepairRunObservation,
    RepairRunResult,
    VerifiedRepairRun,
    run_repair_loop,
)
from aec_bench.harness.compilation import (
    compile_execution_program,
    compile_harness_instance,
    compile_run_plan,
)
from aec_bench.harness.kernel_catalogue import KernelRuntimeRegistry, default_kernel_registry


@pytest.mark.parametrize(
    ("owner", "patch_event", "mutation_scope"),
    [
        (RepairOwner.HARNESS, "patch_hx", RepairMutationScope.HARNESS),
        (RepairOwner.PROGRAM, "patch_px", RepairMutationScope.PROGRAM),
    ],
)
def test_closed_repair_loop_uses_real_compilers_and_patches_only_diagnosed_owner(
    tmp_path: Path,
    owner: RepairOwner,
    patch_event: str,
    mutation_scope: RepairMutationScope,
) -> None:
    workflow = _DeterministicWorkflow(tmp_path=tmp_path, owner=owner)

    result = run_repair_loop(workflow.request, dependencies=workflow.dependencies)

    assert result.status is RepairLoopStatus.ACCEPTED
    assert result.parent_candidate_id == "candidate.parent"
    assert result.child_candidate_id == "candidate.child"
    assert result.iteration == 1
    assert result.diagnosis is not None
    assert result.diagnosis.owner is owner
    assert result.attempt is not None
    assert result.attempt.mutation_scope is mutation_scope
    assert result.attempt.parent_candidate_id == "candidate.parent"
    assert result.attempt.child_candidate_id == "candidate.child"
    assert result.decision is not None
    assert result.decision.accepted is True
    assert workflow.calls == [
        "propose",
        "compile:candidate.parent",
        "run:candidate.parent",
        "verify:candidate.parent",
        "diagnose",
        patch_event,
        "compile:candidate.child",
        "run:candidate.child",
        "verify:candidate.child",
    ]
    assert workflow.child is not None
    if owner is RepairOwner.HARNESS:
        assert workflow.child.harness_request != workflow.parent.harness_request
        assert workflow.child.program_template == workflow.parent.program_template
    else:
        assert workflow.child.harness_request == workflow.parent.harness_request
        assert workflow.child.program_template != workflow.parent.program_template


def test_repair_pairing_prohibits_holdout_before_dependencies_can_run() -> None:
    with pytest.raises(ValidationError, match="holdout"):
        RepairPairingSpec(
            split="holdout",
            task_ids=("civil/calculation/repair",),
            seeds=(17,),
            budget=HarnessBudget(),
            repetitions=1,
        )


@pytest.mark.parametrize("drift", ["tasks", "seeds", "budget", "repetitions"])
def test_runner_must_preserve_exact_pairing_identity(tmp_path: Path, drift: str) -> None:
    workflow = _DeterministicWorkflow(tmp_path=tmp_path, owner=RepairOwner.PROGRAM)
    workflow.run_pairing_override = _drift_pairing(workflow.pairing, drift)

    with pytest.raises(RepairLoopError) as captured:
        run_repair_loop(workflow.request, dependencies=workflow.dependencies)

    assert captured.value.diagnostic.code == "run_pairing_mismatch"
    assert workflow.calls == ["propose", "compile:candidate.parent", "run:candidate.parent"]


def test_pre_mutation_verification_cannot_decide_post_mutation_candidate(tmp_path: Path) -> None:
    workflow = _DeterministicWorkflow(tmp_path=tmp_path, owner=RepairOwner.PROGRAM)
    workflow.reuse_parent_verification_for_child = True

    with pytest.raises(RepairLoopError) as captured:
        run_repair_loop(workflow.request, dependencies=workflow.dependencies)

    assert captured.value.diagnostic.code == "verification_candidate_mismatch"
    assert workflow.calls[-1] == "verify:candidate.child"


def test_verification_must_pin_the_current_run_artifact(tmp_path: Path) -> None:
    workflow = _DeterministicWorkflow(tmp_path=tmp_path, owner=RepairOwner.PROGRAM)
    workflow.reuse_parent_artifact_for_child = True

    with pytest.raises(RepairLoopError) as captured:
        run_repair_loop(workflow.request, dependencies=workflow.dependencies)

    assert captured.value.diagnostic.code == "verification_artifact_mismatch"
    assert workflow.calls[-1] == "verify:candidate.child"


def test_failed_child_verifier_forces_a_typed_rejection(tmp_path: Path) -> None:
    workflow = _DeterministicWorkflow(tmp_path=tmp_path, owner=RepairOwner.PROGRAM)
    workflow.child_passes = False

    result = run_repair_loop(workflow.request, dependencies=workflow.dependencies)

    assert result.status is RepairLoopStatus.REJECTED
    assert result.decision is not None
    assert result.decision.accepted is False
    assert "child_verifier_failed" in result.decision.reasons


def test_incomplete_child_evidence_terminalizes_without_a_scored_decision(tmp_path: Path) -> None:
    workflow = _DeterministicWorkflow(tmp_path=tmp_path, owner=RepairOwner.HARNESS)
    workflow.child_passes = False
    workflow.child_reward_coverage = RepairRewardCoverage.NONE
    workflow.child_execution_status = RepairExecutionStatus.FAILED

    result = run_repair_loop(workflow.request, dependencies=workflow.dependencies)

    assert result.status is RepairLoopStatus.CHILD_EVIDENCE_INCOMPLETE
    assert result.child_verification is not None
    assert result.child_verification.reward_coverage is RepairRewardCoverage.NONE
    assert result.attempt is None
    assert result.decision is None
    assert result.recovery_attempt is None
    assert result.recovery_decision is None


def test_accepted_result_requires_a_passing_child_verification(tmp_path: Path) -> None:
    workflow = _DeterministicWorkflow(tmp_path=tmp_path, owner=RepairOwner.PROGRAM)
    result = run_repair_loop(workflow.request, dependencies=workflow.dependencies)
    payload = result.model_dump(mode="python")
    assert payload["child_verification"] is not None
    payload["child_verification"]["passed"] = False

    with pytest.raises(ValidationError, match="passing child verification"):
        RepairLoopResult.model_validate(payload)


@pytest.mark.parametrize("verification_field", ["parent_verification", "child_verification"])
def test_scored_result_requires_complete_parent_and_child_reward_coverage(
    tmp_path: Path,
    verification_field: str,
) -> None:
    workflow = _DeterministicWorkflow(tmp_path=tmp_path, owner=RepairOwner.PROGRAM)
    result = run_repair_loop(workflow.request, dependencies=workflow.dependencies)
    payload = result.model_dump(mode="python")
    verification = payload[verification_field]
    assert verification is not None
    verification["passed"] = False
    verification["reward_coverage"] = RepairRewardCoverage.PARTIAL
    verification["observations"] = verification["observations"][:1]
    verification["execution_observations"] = [
        RepairExecutionObservation(
            repetition=repetition,
            seed=seed,
            status=RepairExecutionStatus.SUCCEEDED,
        ).model_dump(mode="python")
        for repetition, seed in enumerate(workflow.pairing.seeds, start=1)
    ]
    if verification_field == "child_verification":
        payload["status"] = RepairLoopStatus.REJECTED
        assert payload["decision"] is not None
        payload["decision"]["accepted"] = False
        payload["decision"]["reasons"] = ("child_verifier_failed",)

    with pytest.raises(ValidationError, match="complete reward coverage"):
        RepairLoopResult.model_validate(payload)


def test_child_evidence_incomplete_status_cannot_hide_complete_child_rewards(tmp_path: Path) -> None:
    workflow = _DeterministicWorkflow(tmp_path=tmp_path, owner=RepairOwner.HARNESS)
    result = run_repair_loop(workflow.request, dependencies=workflow.dependencies)
    payload = result.model_dump(mode="python")
    payload["status"] = RepairLoopStatus.CHILD_EVIDENCE_INCOMPLETE
    payload["attempt"] = None
    payload["decision"] = None

    with pytest.raises(ValidationError, match="incomplete child reward coverage"):
        RepairLoopResult.model_validate(payload)


def test_scored_result_binds_attempt_outcomes_to_verification_observations(tmp_path: Path) -> None:
    workflow = _DeterministicWorkflow(tmp_path=tmp_path, owner=RepairOwner.PROGRAM)
    result = run_repair_loop(workflow.request, dependencies=workflow.dependencies)
    payload = result.model_dump(mode="python")
    child_verification = payload["child_verification"]
    assert child_verification is not None
    child_verification["observations"][0]["outcome"]["reward"] = 0.7

    with pytest.raises(ValidationError, match="child outcomes must equal"):
        RepairLoopResult.model_validate(payload)


def test_passing_parent_stops_without_diagnosis_or_mutation(tmp_path: Path) -> None:
    workflow = _DeterministicWorkflow(tmp_path=tmp_path, owner=RepairOwner.PROGRAM)
    workflow.parent_passes = True

    result = run_repair_loop(workflow.request, dependencies=workflow.dependencies)

    assert result.status is RepairLoopStatus.NO_REPAIR_REQUIRED
    assert result.child_candidate_id is None
    assert result.decision is None
    assert workflow.calls == [
        "propose",
        "compile:candidate.parent",
        "run:candidate.parent",
        "verify:candidate.parent",
    ]


@pytest.mark.parametrize(
    "failure_domain",
    [
        RepairFailureDomain.TASK_WORLD,
        RepairFailureDomain.VERIFIER,
        RepairFailureDomain.RUNTIME,
        RepairFailureDomain.UNDETERMINED,
    ],
)
def test_unowned_failure_domain_stops_without_mutating_harness_or_program(
    tmp_path: Path,
    failure_domain: RepairFailureDomain,
) -> None:
    workflow = _DeterministicWorkflow(tmp_path=tmp_path, owner=None)
    workflow.failure_domain = failure_domain

    result = run_repair_loop(workflow.request, dependencies=workflow.dependencies)

    assert result.status is RepairLoopStatus.NO_APPLICABLE_REPAIR
    assert result.diagnosis is not None
    assert result.diagnosis.failure_domain is failure_domain
    assert result.diagnosis.owner is None
    assert result.diagnosis.evidence_codes == ("healthy_runtime_low_reward",)
    assert result.child_candidate_id is None
    assert result.child_verification is None
    assert result.attempt is None
    assert result.decision is None
    assert workflow.calls == [
        "propose",
        "compile:candidate.parent",
        "run:candidate.parent",
        "verify:candidate.parent",
        "diagnose",
    ]


def test_repair_diagnosis_rejects_owner_that_disagrees_with_failure_domain() -> None:
    with pytest.raises(ValidationError, match="failure domain"):
        RepairDiagnosis(
            candidate_id="candidate.parent",
            run_id="run.parent",
            failure_domain=RepairFailureDomain.PROGRAM,
            owner=RepairOwner.HARNESS,
            code="contradictory_owner",
            message="The claimed mutable owner disagrees with the evidence domain.",
            evidence_codes=("program_node_failed",),
        )


@pytest.mark.parametrize("failure_domain", [RepairFailureDomain.HARNESS, RepairFailureDomain.PROGRAM])
def test_mutable_failure_domain_can_abstain_when_no_typed_patch_applies(
    tmp_path: Path,
    failure_domain: RepairFailureDomain,
) -> None:
    workflow = _DeterministicWorkflow(tmp_path=tmp_path, owner=None)
    workflow.failure_domain = failure_domain

    result = run_repair_loop(workflow.request, dependencies=workflow.dependencies)

    assert result.status is RepairLoopStatus.NO_APPLICABLE_REPAIR
    assert result.diagnosis is not None
    assert result.diagnosis.failure_domain is failure_domain
    assert result.diagnosis.owner is None
    assert result.child_candidate_id is None
    assert workflow.calls[-1] == "diagnose"


def test_program_failure_uses_execution_recovery_without_synthesizing_parent_rewards(
    tmp_path: Path,
) -> None:
    workflow = _DeterministicWorkflow(tmp_path=tmp_path, owner=RepairOwner.PROGRAM)
    workflow.parent_reward_coverage = RepairRewardCoverage.NONE
    workflow.parent_execution_status = RepairExecutionStatus.FAILED
    workflow.child_execution_status = RepairExecutionStatus.SUCCEEDED

    result = run_repair_loop(workflow.request, dependencies=workflow.dependencies)

    assert result.status is RepairLoopStatus.RECOVERED_UNSCORED
    assert result.parent_verification.reward_coverage is RepairRewardCoverage.NONE
    assert result.parent_verification.observations == ()
    assert result.child_verification is not None
    assert result.child_verification.reward_coverage is RepairRewardCoverage.COMPLETE
    assert len(result.child_verification.observations) == 2
    assert result.attempt is None
    assert result.decision is None
    assert result.recovery_attempt is not None
    assert result.recovery_attempt.parent_executions == result.parent_verification.execution_observations
    assert result.recovery_attempt.child_executions == result.child_verification.execution_observations
    assert result.recovery_decision is not None
    assert result.recovery_decision.recovered is True
    assert result.recovery_decision.parent_failed_count == 2
    assert result.recovery_decision.child_succeeded_count == 2


def test_program_execution_recovery_fails_when_child_execution_is_not_successful(
    tmp_path: Path,
) -> None:
    workflow = _DeterministicWorkflow(tmp_path=tmp_path, owner=RepairOwner.PROGRAM)
    workflow.parent_reward_coverage = RepairRewardCoverage.PARTIAL
    workflow.parent_execution_status = RepairExecutionStatus.FAILED
    workflow.child_execution_status = RepairExecutionStatus.FAILED
    workflow.child_passes = False

    result = run_repair_loop(workflow.request, dependencies=workflow.dependencies)

    assert result.status is RepairLoopStatus.RECOVERY_FAILED
    assert len(result.parent_verification.observations) == 1
    assert result.attempt is None
    assert result.decision is None
    assert result.recovery_decision is not None
    assert result.recovery_decision.recovered is False
    assert "child_execution_incomplete" in result.recovery_decision.reasons
    assert "child_verifier_failed" in result.recovery_decision.reasons


def test_recovery_result_binds_attempt_executions_to_verification_observations(
    tmp_path: Path,
) -> None:
    workflow = _DeterministicWorkflow(tmp_path=tmp_path, owner=RepairOwner.PROGRAM)
    workflow.parent_reward_coverage = RepairRewardCoverage.NONE
    workflow.parent_execution_status = RepairExecutionStatus.FAILED
    workflow.child_execution_status = RepairExecutionStatus.SUCCEEDED
    result = run_repair_loop(workflow.request, dependencies=workflow.dependencies)
    payload = result.model_dump(mode="python")
    assert payload["recovery_attempt"] is not None
    payload["recovery_attempt"]["child_executions"] = tuple(reversed(payload["recovery_attempt"]["child_executions"]))

    with pytest.raises(ValidationError, match="child executions must equal"):
        RepairLoopResult.model_validate(payload)


def test_recovered_unscored_requires_a_complete_passing_child(tmp_path: Path) -> None:
    workflow = _DeterministicWorkflow(tmp_path=tmp_path, owner=RepairOwner.PROGRAM)
    workflow.parent_reward_coverage = RepairRewardCoverage.NONE
    workflow.parent_execution_status = RepairExecutionStatus.FAILED
    workflow.child_execution_status = RepairExecutionStatus.SUCCEEDED
    result = run_repair_loop(workflow.request, dependencies=workflow.dependencies)
    payload = result.model_dump(mode="python")
    assert payload["child_verification"] is not None
    payload["child_verification"]["passed"] = False

    with pytest.raises(ValidationError, match="complete passing child verification"):
        RepairLoopResult.model_validate(payload)


def test_incomplete_reward_coverage_requires_exact_execution_observations(tmp_path: Path) -> None:
    workflow = _DeterministicWorkflow(tmp_path=tmp_path, owner=RepairOwner.PROGRAM)
    compiled = workflow.compile(workflow.parent, workflow.pairing)
    run = workflow.run(compiled, workflow.pairing)

    with pytest.raises(ValidationError, match="execution observations"):
        VerifiedRepairRun(
            verification_id="verification.incomplete",
            run_id=run.run_id,
            candidate_id=compiled.candidate_id,
            harness_ref=compiled.harness.ref,
            program_ref=compiled.program.ref,
            run_artifact_sha256=run.artifact_sha256,
            pairing=run.pairing,
            passed=False,
            reward_coverage=RepairRewardCoverage.NONE,
            observations=(),
            execution_observations=(),
        )


def test_patcher_cannot_mutate_the_non_owned_surface(tmp_path: Path) -> None:
    workflow = _DeterministicWorkflow(tmp_path=tmp_path, owner=RepairOwner.PROGRAM)
    workflow.mutate_both_surfaces = True

    with pytest.raises(RepairLoopError) as captured:
        run_repair_loop(workflow.request, dependencies=workflow.dependencies)

    assert captured.value.diagnostic.code == "non_owned_harness_mutated"
    assert workflow.calls[-1] == "patch_px"


class _DeterministicWorkflow:
    def __init__(self, *, tmp_path: Path, owner: RepairOwner | None) -> None:
        self.registry = default_kernel_registry()
        self.tasks_root = tmp_path / "tasks"
        self.task_id = "civil/calculation/repair"
        _write_task(self.tasks_root, self.task_id)
        self.pairing = RepairPairingSpec(
            split="repair_gate",
            task_ids=(self.task_id,),
            seeds=(17, 29),
            budget=HarnessBudget(),
            repetitions=2,
        )
        self.parent = _parent_candidate(self.registry, self.pairing)
        self.owner = owner
        self.failure_domain = (
            RepairFailureDomain(owner.value) if owner is not None else RepairFailureDomain.UNDETERMINED
        )
        self.calls: list[str] = []
        self.child: RepairCandidate | None = None
        self.parent_verification: VerifiedRepairRun | None = None
        self.run_pairing_override: RepairPairingSpec | None = None
        self.reuse_parent_verification_for_child = False
        self.reuse_parent_artifact_for_child = False
        self.parent_passes = False
        self.child_passes = True
        self.parent_reward_coverage = RepairRewardCoverage.COMPLETE
        self.child_reward_coverage = RepairRewardCoverage.COMPLETE
        self.parent_execution_status: RepairExecutionStatus | None = None
        self.child_execution_status: RepairExecutionStatus | None = None
        self.mutate_both_surfaces = False
        self.request = RepairLoopRequest(
            loop_id="loop.1",
            attempt_id="repair.1",
            iteration=1,
            parent_candidate_id="candidate.parent",
            child_candidate_id="candidate.child",
            pairing=self.pairing,
            acceptance_policy=RepairAcceptancePolicy(
                minimum_mean_reward_delta=0.1,
                bootstrap_replicates=100,
            ),
        )
        self.dependencies = RepairLoopDependencies(
            generator=self.propose,
            compiler=self.compile,
            runner=self.run,
            verifier=self.verify,
            diagnoser=self.diagnose,
            harness_patcher=self.patch_harness,
            program_patcher=self.patch_program,
        )

    def propose(self, request: RepairLoopRequest) -> RepairCandidate:
        self.calls.append("propose")
        return self.parent

    def compile(
        self,
        candidate: RepairCandidate,
        pairing: RepairPairingSpec,
    ) -> CompiledRepairCandidate:
        self.calls.append(f"compile:{candidate.candidate_id}")
        harness = compile_harness_instance(candidate.harness_request, registry=self.registry)
        source_program = candidate.program_template.bind(harness.ref)
        program = compile_execution_program(source_program, harness=harness, registry=self.registry)
        bundle = compile_run_plan(
            run_id=f"bundle.{candidate.candidate_id}",
            harness=harness,
            execution_program=program,
            registry=self.registry,
            tasks_root=self.tasks_root,
            experiment_id="repair-loop",
        )
        return CompiledRepairCandidate(
            candidate_id=candidate.candidate_id,
            parent_candidate_id=candidate.parent_candidate_id,
            iteration=candidate.iteration,
            harness=harness,
            program=program,
            bundle=bundle,
        )

    def run(
        self,
        candidate: CompiledRepairCandidate,
        pairing: RepairPairingSpec,
    ) -> RepairRunResult:
        self.calls.append(f"run:{candidate.candidate_id}")
        return RepairRunResult(
            run_id=f"run.{candidate.candidate_id}",
            candidate_id=candidate.candidate_id,
            pairing=self.run_pairing_override or pairing,
            artifact_sha256=_sha(f"artifact:{candidate.candidate_id}"),
        )

    def verify(
        self,
        candidate: CompiledRepairCandidate,
        run: RepairRunResult,
    ) -> VerifiedRepairRun:
        self.calls.append(f"verify:{candidate.candidate_id}")
        if self.reuse_parent_verification_for_child and candidate.candidate_id == "candidate.child":
            assert self.parent_verification is not None
            return self.parent_verification

        reward = 0.2 if candidate.candidate_id == "candidate.parent" else 0.8
        snapshots = {snapshot.task_id: snapshot for snapshot in candidate.bundle.task_snapshots}
        complete_observations = tuple(
            RepairRunObservation(
                seed=seed,
                outcome=RepairTrialOutcome(
                    block_id=f"block:{task_id}:{repetition}:{seed}",
                    task_world_id=task_id,
                    repetition=repetition,
                    split=run.pairing.split,
                    candidate_id=candidate.candidate_id,
                    kernel_ref=candidate.harness.kernel_ref,
                    resource_sha256=snapshots[task_id].commitment_sha256,
                    review_lineage_sha256=_review_lineage_sha256(snapshots[task_id]),
                    reward=reward,
                    complete=True,
                    valid=True,
                    cost=1.0,
                ),
            )
            for task_id in run.pairing.task_ids
            for repetition, seed in enumerate(run.pairing.seeds, start=1)
        )
        reward_coverage = (
            self.parent_reward_coverage if candidate.candidate_id == "candidate.parent" else self.child_reward_coverage
        )
        observations = {
            RepairRewardCoverage.COMPLETE: complete_observations,
            RepairRewardCoverage.PARTIAL: complete_observations[:1],
            RepairRewardCoverage.NONE: (),
        }[reward_coverage]
        execution_status = (
            self.parent_execution_status
            if candidate.candidate_id == "candidate.parent"
            else self.child_execution_status
        )
        execution_observations = (
            tuple(
                RepairExecutionObservation(
                    repetition=repetition,
                    seed=seed,
                    status=execution_status,
                    error_code=(
                        "global_attempt_budget_exhausted"
                        if execution_status is not RepairExecutionStatus.SUCCEEDED
                        else None
                    ),
                    failed_node_id=("run" if execution_status is not RepairExecutionStatus.SUCCEEDED else None),
                )
                for repetition, seed in enumerate(run.pairing.seeds, start=1)
            )
            if execution_status is not None
            else ()
        )
        verification = VerifiedRepairRun(
            verification_id=f"verification.{candidate.candidate_id}",
            run_id=run.run_id,
            candidate_id=candidate.candidate_id,
            harness_ref=candidate.harness.ref,
            program_ref=candidate.program.ref,
            run_artifact_sha256=(
                self.parent_verification.run_artifact_sha256
                if self.reuse_parent_artifact_for_child and self.parent_verification is not None
                else run.artifact_sha256
            ),
            pairing=run.pairing,
            passed=(self.parent_passes if candidate.candidate_id == "candidate.parent" else self.child_passes),
            reward_coverage=reward_coverage,
            observations=observations,
            execution_observations=execution_observations,
        )
        if candidate.candidate_id == "candidate.parent":
            self.parent_verification = verification
        return verification

    def diagnose(
        self,
        candidate: CompiledRepairCandidate,
        verification: VerifiedRepairRun,
    ) -> RepairDiagnosis:
        self.calls.append("diagnose")
        return RepairDiagnosis(
            candidate_id=candidate.candidate_id,
            run_id=verification.run_id,
            failure_domain=self.failure_domain,
            owner=self.owner,
            code="verifier_failure",
            message="Verifier attributed the failure to one mutable surface.",
            evidence_codes=("healthy_runtime_low_reward",),
        )

    def patch_harness(self, request: RepairPatchRequest) -> RepairCandidate:
        self.calls.append("patch_hx")
        child = RepairCandidate(
            candidate_id=request.child_candidate_id,
            parent_candidate_id=request.parent.candidate_id,
            iteration=request.iteration,
            harness_request=_patched_harness_request(request.parent.harness_request),
            program_template=request.parent.program_template,
        )
        self.child = child
        return child

    def patch_program(self, request: RepairPatchRequest) -> RepairCandidate:
        self.calls.append("patch_px")
        harness_request = (
            _patched_harness_request(request.parent.harness_request)
            if self.mutate_both_surfaces
            else request.parent.harness_request
        )
        child = RepairCandidate(
            candidate_id=request.child_candidate_id,
            parent_candidate_id=request.parent.candidate_id,
            iteration=request.iteration,
            harness_request=harness_request,
            program_template=_patched_program_template(request.parent.program_template),
        )
        self.child = child
        return child


def _parent_candidate(
    registry: KernelRuntimeRegistry,
    pairing: RepairPairingSpec,
) -> RepairCandidate:
    recipe = _recipe(registry, task_id=pairing.task_ids[0], budget=pairing.budget)
    return RepairCandidate(
        candidate_id="candidate.parent",
        parent_candidate_id=None,
        iteration=0,
        harness_request=HarnessCompileRequest(
            request_id="compile-parent",
            kernel_ref=registry.manifest.ref,
            spec=recipe,
        ),
        program_template=RepairProgramTemplate(
            program_id="px-repair",
            version="1.0.0",
            nodes=(
                ActionNode(node_id="run", operation_id="run_batch"),
                StopNode(node_id="stop", depends_on=("run",), outcome=StopOutcome.SUCCEEDED),
            ),
            limits=ProgramLimits(max_total_attempts=1),
        ),
    )


def _patched_harness_request(parent: HarnessCompileRequest) -> HarnessCompileRequest:
    bindings: list[HarnessBindingSpec] = []
    for binding in parent.spec.bindings:
        configuration = binding.configuration
        if isinstance(configuration, AgentBindingConfig):
            configuration = AgentBindingConfig(
                agent_name=configuration.agent_name,
                model=configuration.model,
                max_turns=configuration.max_turns + 1,
                timeout_seconds=configuration.timeout_seconds,
            )
        bindings.append(
            HarnessBindingSpec(
                binding_id=binding.binding_id,
                capability_ref=binding.capability_ref,
                depends_on=binding.depends_on,
                topology_role=binding.topology_role,
                contract_ids=binding.contract_ids,
                configuration=configuration,
            )
        )
    recipe = HarnessSpec(
        summary=parent.spec.summary,
        contracts=parent.spec.contracts,
        budget=parent.spec.budget,
        recursion_policy=parent.spec.recursion_policy,
        bindings=tuple(bindings),
    )
    return HarnessCompileRequest(
        request_id="compile-child-hx",
        kernel_ref=parent.kernel_ref,
        spec=recipe,
    )


def _patched_program_template(parent: RepairProgramTemplate) -> RepairProgramTemplate:
    return RepairProgramTemplate(
        program_id=parent.program_id,
        version=parent.version,
        nodes=parent.nodes,
        limits=ProgramLimits(
            max_nodes=parent.limits.max_nodes,
            max_parallelism=parent.limits.max_parallelism,
            max_total_attempts=parent.limits.max_total_attempts + 1,
            max_recursion_depth=parent.limits.max_recursion_depth,
            max_recursive_calls=parent.limits.max_recursive_calls,
        ),
    )


def _recipe(
    registry: KernelRuntimeRegistry,
    *,
    task_id: str,
    budget: HarnessBudget,
) -> HarnessSpec:
    capability = registry.capability
    return HarnessSpec(
        summary="Run one paired repair task through the fixed Harbor kernel.",
        budget=budget,
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
                configuration=ContextBindingConfig(
                    source_ids=("workspace.system_prompt",),
                    max_tokens=4_000,
                ),
            ),
            HarnessBindingSpec(
                binding_id="tools",
                capability_ref=capability("aecbench.tools.task-declared").ref,
                depends_on=("tasks",),
                topology_role=HarnessTopologyRole.SERVICE,
                configuration=ToolBindingConfig(
                    tool_ids=("bash",),
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
                    agent_name="repair-tool-loop",
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
                configuration=ResultImportBindingConfig(ledger_namespace="repair-loop"),
            ),
        ),
    )


def _drift_pairing(pairing: RepairPairingSpec, drift: str) -> RepairPairingSpec:
    if drift == "tasks":
        return RepairPairingSpec(
            split=pairing.split,
            task_ids=("civil/calculation/other",),
            seeds=pairing.seeds,
            budget=pairing.budget,
            repetitions=pairing.repetitions,
        )
    if drift == "seeds":
        return RepairPairingSpec(
            split=pairing.split,
            task_ids=pairing.task_ids,
            seeds=(31, 43),
            budget=pairing.budget,
            repetitions=pairing.repetitions,
        )
    if drift == "budget":
        return RepairPairingSpec(
            split=pairing.split,
            task_ids=pairing.task_ids,
            seeds=pairing.seeds,
            budget=pairing.budget.model_copy(update={"max_tool_calls": pairing.budget.max_tool_calls + 1}),
            repetitions=pairing.repetitions,
        )
    return RepairPairingSpec(
        split=pairing.split,
        task_ids=pairing.task_ids,
        seeds=(pairing.seeds[0],),
        budget=pairing.budget,
        repetitions=1,
    )


def _write_task(tasks_root: Path, task_id: str) -> None:
    task_dir = tasks_root / task_id
    (task_dir / "environment" / "tools").mkdir(parents=True)
    (task_dir / "tests").mkdir()
    (task_dir / "task.toml").write_text(
        """
[metadata]
difficulty = "easy"
visibility = "public"
tags = ["repair"]

[agent]
timeout_sec = 300

[[environment.tools]]
name = "bash"
source = "environment/tools/bash.sh"
description = "Run task-declared shell commands inside the isolated workspace."
returns_image = false
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (task_dir / "instruction.md").write_text("Solve and write /workspace/output.md.\n", encoding="utf-8")
    (task_dir / "environment" / "Dockerfile").write_text("FROM python:3.13-slim\n", encoding="utf-8")
    (task_dir / "environment" / "system_prompt.md").write_text("Use evidence.\n", encoding="utf-8")
    (task_dir / "environment" / "tools" / "bash.sh").write_text(
        '#!/bin/sh\nexec /bin/sh -lc "$1"\n',
        encoding="utf-8",
    )
    (task_dir / "tests" / "test.sh").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    (task_dir / "tests" / "test.sh").chmod(0o755)


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _review_lineage_sha256(snapshot: TaskSnapshotRef) -> str:
    return snapshot.commitment_sha256
