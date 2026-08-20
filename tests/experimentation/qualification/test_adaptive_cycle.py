# ABOUTME: Exercises the fixed-K adaptive-cycle orchestrator through governed promotion handoff.
# ABOUTME: Proves repair, calibration, and motif evidence stop before authority-bearing status changes.

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from aec_bench.contracts.execution_program import (
    ActionNode,
    LiteralValue,
    ProgramArgument,
    StopNode,
    StopOutcome,
)
from aec_bench.evolution.paired_repair import RepairAcceptancePolicy
from aec_bench.evolution.repair_lifecycle import (
    RepairCandidate,
    RepairLoopError,
    RepairProgramTemplate,
)
from aec_bench.experimentation.governance.applicability import profile_task_applicability
from aec_bench.experimentation.governance.motifs import (
    MotifLibrary,
    MotifStatus,
    write_motif_library_artifact,
)
from aec_bench.experimentation.qualification.adaptive_cycle_cli import run_cli
from aec_bench.experimentation.qualification.adaptive_cycle_runtime import (
    AdaptiveCycleExecutors,
    AdaptiveCycleOutcome,
    AdaptiveCycleSpec,
    AdaptiveCycleTerminalReason,
    AdaptiveCycleTerminalStage,
    AdaptiveHarnessProgramStageSpec,
    HarnessMaxTurnsDiagnosisRule,
    load_adaptive_cycle_report,
    materialize_child_harness_program_request,
)
from aec_bench.experimentation.qualification.adaptive_diagnosis import (
    AdaptiveDiagnosisPolicy,
)
from aec_bench.experimentation.qualification.harness_program_study import (
    prepare_harness_program_study_spec as prepare_harness_program_study_spec,
)
from aec_bench.experimentation.qualification.harness_program_study.candidates import (
    HarnessProgramCandidateRequest,
    ProgramFactorTemplate,
)
from aec_bench.experimentation.qualification.motif_materialization import MotifHarnessProgramInstantiationRequest
from aec_bench.experimentation.qualification.repair_runtime import RepairVerifierPolicy
from tests.experimentation.qualification.test_harness_program_study import HarnessProgramStudyHarborExecutor
from tests.experimentation.qualification.test_motif_learning import (
    _agent_model,
    _fanout_factor,
    _fixed_harness_spec,
    _policy,
    _program_factor,
    _rebind_recipe_tasks,
)
from tests.experimentation.qualification.test_repair_runtime import (
    RewardByTurnsHarborExecutor,
    _build_runtime,
    _write_task,
)


class TaskDriftAfterSourceExecutor(HarnessProgramStudyHarborExecutor):
    """Changes one source task only after every preregistered source-cell execution completes."""

    def __init__(self, task_instruction: Path, *, expected_calls: int) -> None:
        super().__init__()
        self.task_instruction = Path(task_instruction)
        self.expected_calls = expected_calls
        self.completed_calls = 0
        self._completion_lock = threading.Lock()

    def execute(self, *, command: list[str], cwd: Path) -> int:
        exit_code = super().execute(command=command, cwd=cwd)
        with self._completion_lock:
            self.completed_calls += 1
            if self.completed_calls == self.expected_calls:
                self.task_instruction.write_text(
                    self.task_instruction.read_text(encoding="utf-8")
                    + "Changed between source search and paired repair.\n",
                    encoding="utf-8",
                )
        return exit_code


def test_child_harness_program_study_rebinds_only_typed_repaired_program_task_inputs(
    tmp_path: Path,
) -> None:
    fixture_runtime = _build_runtime(
        tmp_path / "fixture",
        executor=RewardByTurnsHarborExecutor(),
        diagnosis=lambda _evidence: (_ for _ in ()).throw(AssertionError("fixture diagnosis must not run")),
    )
    parent = fixture_runtime.parent
    registry = fixture_runtime.registry
    source_task = fixture_runtime.request.pairing.task_ids[0]
    child_task = "civil/calculation/adaptive-cycle-program-child"
    _write_task(fixture_runtime.tasks_root, child_task)
    repaired = RepairCandidate(
        candidate_id="candidate.child.literal-task-input",
        parent_candidate_id=parent.candidate_id,
        iteration=1,
        harness_request=parent.harness_request,
        program_template=RepairProgramTemplate(
            program_id=parent.program_template.program_id,
            version=parent.program_template.version,
            nodes=(
                ActionNode(
                    node_id="run",
                    operation_id="run_batch",
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
                StopNode(
                    node_id="stop",
                    depends_on=("run",),
                    outcome=StopOutcome.SUCCEEDED,
                ),
            ),
            limits=parent.program_template.limits,
        ),
    )
    fixed_harness = _rebind_recipe_tasks(
        _fixed_harness_spec(parent, registry),
        task_refs=(child_task,),
    )
    stage = AdaptiveHarnessProgramStageSpec(
        policy_id="policy.adaptive-cycle.program-child",
        split="calibration",
        instantiation=MotifHarnessProgramInstantiationRequest(
            candidate_set_id="adaptive-cycle.program-child",
            task_set_id="world-program-child",
            experiment_id="adaptive-cycle-program-child",
            kernel_ref=registry.manifest.ref,
            task_refs=(child_task,),
            model=_agent_model(parent),
            harness_budget=fixture_runtime.request.pairing.budget,
            program_limits=parent.program_template.limits,
            seeds=(43,),
            repetitions=1,
            fixed_harness_spec=fixed_harness,
            fixed_program=_fanout_factor(parent.program_template.limits),
        ),
        applicability=profile_task_applicability(
            task_refs=(child_task,),
            tasks_root=fixture_runtime.tasks_root,
            registry=registry,
        ),
        randomization_seed=79,
        bootstrap_replicates=8,
    )

    request = materialize_child_harness_program_request(stage, repaired)

    run = request.learned_program.nodes[0]
    assert isinstance(run, ActionNode)
    assert run.arguments == (
        ProgramArgument(name="task_ref", value=LiteralValue(value=child_task)),
        ProgramArgument(name="diagnostic_label", value=LiteralValue(value=source_task)),
    )


def test_adaptive_cycle_runs_and_persists_the_complete_fixed_k_example(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fixture_runtime = _build_runtime(
        tmp_path / "fixture",
        executor=RewardByTurnsHarborExecutor(),
        diagnosis=lambda _evidence: (_ for _ in ()).throw(AssertionError("fixture diagnosis must not run")),
        task_ids=(
            "civil/calculation/adaptive-cycle-source-a",
            "civil/calculation/adaptive-cycle-source-b",
        ),
    )
    parent = fixture_runtime.parent
    registry = fixture_runtime.registry
    for index, task_id in enumerate(fixture_runtime.request.pairing.task_ids, start=1):
        _write_world_sidecar(fixture_runtime.tasks_root / task_id, label=f"source-{index}")
    parent_program = _program_factor(parent.program_template)
    fixed_harness = _fixed_harness_spec(parent, registry)
    fixed_program = _fanout_factor(parent.program_template.limits)
    source_request = HarnessProgramCandidateRequest(
        candidate_set_id="adaptive-cycle.source",
        task_set_id="world-source",
        experiment_id="adaptive-cycle-source",
        kernel_ref=registry.manifest.ref,
        task_refs=fixture_runtime.request.pairing.task_ids,
        model=_agent_model(parent),
        harness_budget=fixture_runtime.request.pairing.budget,
        program_limits=parent.program_template.limits,
        seeds=(41,),
        repetitions=1,
        fixed_harness_spec=fixed_harness,
        learned_harness_spec=parent.harness_request.spec,
        fixed_program=fixed_program,
        learned_program=parent_program,
    )
    source_spec = prepare_harness_program_study_spec(
        candidate_requests=(source_request,),
        registry=registry,
        tasks_root=fixture_runtime.tasks_root,
        policy_id="policy.adaptive-cycle.source",
        randomization_seed=73,
        harness_generator_sha256="1" * 64,
        program_generator_sha256="2" * 64,
        split="discovery",
        bootstrap_replicates=8,
    )
    calibration_tasks = (
        "civil/calculation/adaptive-cycle-calibration-a",
        "civil/calculation/adaptive-cycle-calibration-b",
    )
    for index, task_id in enumerate(calibration_tasks, start=1):
        _write_task(fixture_runtime.tasks_root, task_id)
        _write_world_sidecar(fixture_runtime.tasks_root / task_id, label=f"calibration-{index}")
    child_stage = AdaptiveHarnessProgramStageSpec(
        policy_id="policy.adaptive-cycle.child",
        split="calibration",
        instantiation=MotifHarnessProgramInstantiationRequest(
            candidate_set_id="adaptive-cycle.child",
            task_set_id="world-source",
            experiment_id="adaptive-cycle-child",
            kernel_ref=registry.manifest.ref,
            task_refs=calibration_tasks,
            model=_agent_model(parent),
            harness_budget=fixture_runtime.request.pairing.budget,
            program_limits=parent.program_template.limits,
            seeds=(43,),
            repetitions=1,
            fixed_harness_spec=_rebind_recipe_tasks(fixed_harness, task_refs=calibration_tasks),
            fixed_program=fixed_program,
        ),
        applicability=profile_task_applicability(
            task_refs=calibration_tasks,
            tasks_root=fixture_runtime.tasks_root,
            registry=registry,
        ),
        randomization_seed=79,
        bootstrap_replicates=8,
    )
    mismatched_child_instantiation = MotifHarnessProgramInstantiationRequest(
        candidate_set_id="adaptive-cycle.child.mismatched",
        task_set_id="world-source",
        experiment_id="adaptive-cycle-child",
        kernel_ref=registry.manifest.ref,
        task_refs=calibration_tasks,
        model=_agent_model(parent),
        harness_budget=fixture_runtime.request.pairing.budget,
        program_limits=parent.program_template.limits,
        seeds=(43,),
        repetitions=1,
        fixed_harness_spec=fixed_harness,
        fixed_program=fixed_program,
    )
    with pytest.raises(ValueError, match="fixed harness task-source binding"):
        AdaptiveHarnessProgramStageSpec(
            policy_id="policy.adaptive-cycle.child",
            split="calibration",
            instantiation=mismatched_child_instantiation,
            applicability=child_stage.applicability,
            randomization_seed=79,
            bootstrap_replicates=8,
        )

    target_tasks = (
        "civil/calculation/adaptive-cycle-transfer-a",
        "civil/calculation/adaptive-cycle-transfer-b",
    )
    for index, task_id in enumerate(target_tasks, start=1):
        _write_task(fixture_runtime.tasks_root, task_id)
        task_toml = fixture_runtime.tasks_root / task_id / "task.toml"
        task_toml.write_text(
            task_toml.read_text(encoding="utf-8").replace(
                'visibility = "public"',
                'visibility = "holdout"',
            ),
            encoding="utf-8",
        )
        instruction = fixture_runtime.tasks_root / task_id / "instruction.md"
        instruction.write_text(
            instruction.read_text(encoding="utf-8") + f"Target family {index}.\n",
            encoding="utf-8",
        )
        _write_world_sidecar(fixture_runtime.tasks_root / task_id, label=f"transfer-{index}")
    transfer_stage = AdaptiveHarnessProgramStageSpec(
        policy_id="policy.adaptive-cycle.transfer",
        split="holdout",
        instantiation=MotifHarnessProgramInstantiationRequest(
            candidate_set_id="adaptive-cycle.transfer",
            task_set_id="world-transfer",
            experiment_id="adaptive-cycle-transfer",
            kernel_ref=registry.manifest.ref,
            task_refs=target_tasks,
            model=_agent_model(parent),
            harness_budget=fixture_runtime.request.pairing.budget,
            program_limits=parent.program_template.limits,
            seeds=(47,),
            repetitions=1,
            fixed_harness_spec=_rebind_recipe_tasks(fixed_harness, task_refs=target_tasks),
            fixed_program=fixed_program,
        ),
        applicability=profile_task_applicability(
            task_refs=target_tasks,
            tasks_root=fixture_runtime.tasks_root,
            registry=registry,
        ),
        randomization_seed=101,
        bootstrap_replicates=8,
    )
    input_library = write_motif_library_artifact(
        MotifLibrary.create(),
        artifacts_root=tmp_path / "input-motif-libraries",
    )
    spec = AdaptiveCycleSpec(
        source_stage=source_spec,
        repair_request=fixture_runtime.request,
        repair_parent=parent,
        repair_verifier_policy=RepairVerifierPolicy(minimum_reward=0.8),
        diagnosis_rule=AdaptiveDiagnosisPolicy(
            rules=(
                HarnessMaxTurnsDiagnosisRule(
                    binding_id="agent",
                    max_turns=2,
                ),
            )
        ),
        child_calibration=child_stage,
        promotion_policy=_policy(),
        transfer=transfer_stage,
        input_motif_library=input_library,
        harness_generator_sha256="1" * 64,
        program_generator_sha256="2" * 64,
    )
    single_child_task = (calibration_tasks[0],)
    single_child_stage = AdaptiveHarnessProgramStageSpec(
        policy_id="policy.adaptive-cycle.single-child",
        split="calibration",
        instantiation=MotifHarnessProgramInstantiationRequest(
            candidate_set_id="adaptive-cycle.single-child",
            task_set_id="world-source",
            experiment_id="adaptive-cycle-child",
            kernel_ref=registry.manifest.ref,
            task_refs=single_child_task,
            model=_agent_model(parent),
            harness_budget=fixture_runtime.request.pairing.budget,
            program_limits=parent.program_template.limits,
            seeds=(43,),
            repetitions=1,
            fixed_harness_spec=_rebind_recipe_tasks(
                fixed_harness,
                task_refs=single_child_task,
            ),
            fixed_program=fixed_program,
        ),
        applicability=profile_task_applicability(
            task_refs=single_child_task,
            tasks_root=fixture_runtime.tasks_root,
            registry=registry,
        ),
        randomization_seed=79,
        bootstrap_replicates=8,
    )
    cardinality_payload = spec.model_dump(mode="python", exclude={"content_sha256"})
    cardinality_payload["child_calibration"] = single_child_stage
    with pytest.raises(ValueError, match="one-to-one task cardinality"):
        AdaptiveCycleSpec.model_validate(cardinality_payload)

    unrelated_program_payload = parent_program.model_dump(
        mode="python",
        exclude={"content_sha256"},
    )
    unrelated_program_payload["factor_id"] = "adaptive-cycle.unrelated-program"
    unrelated_source_request = HarnessProgramCandidateRequest(
        candidate_set_id="adaptive-cycle.unrelated-source",
        task_set_id="world-source",
        experiment_id="adaptive-cycle-source",
        kernel_ref=registry.manifest.ref,
        task_refs=fixture_runtime.request.pairing.task_ids,
        model=_agent_model(parent),
        harness_budget=fixture_runtime.request.pairing.budget,
        program_limits=parent.program_template.limits,
        seeds=(41,),
        repetitions=1,
        fixed_harness_spec=fixed_harness,
        learned_harness_spec=parent.harness_request.spec,
        fixed_program=fixed_program,
        learned_program=ProgramFactorTemplate.model_validate(unrelated_program_payload),
    )
    unrelated_source_spec = prepare_harness_program_study_spec(
        candidate_requests=(unrelated_source_request,),
        registry=registry,
        tasks_root=fixture_runtime.tasks_root,
        policy_id="policy.adaptive-cycle.source",
        randomization_seed=73,
        harness_generator_sha256="1" * 64,
        program_generator_sha256="2" * 64,
        split="discovery",
        bootstrap_replicates=8,
    )
    unrelated_source_payload = spec.model_dump(mode="python", exclude={"content_sha256"})
    unrelated_source_payload["source_stage"] = unrelated_source_spec
    with pytest.raises(ValueError, match="repair parent Hx/px"):
        AdaptiveCycleSpec.model_validate(unrelated_source_payload)

    infeasible = spec.model_dump(mode="python", exclude={"content_sha256"})
    infeasible["diagnosis_rule"]["rules"][0]["max_turns"] = 1
    with pytest.raises(ValueError, match="must strictly increase binding max_turns"):
        AdaptiveCycleSpec.model_validate(infeasible)
    source_executor = HarnessProgramStudyHarborExecutor()
    repair_executor = RewardByTurnsHarborExecutor(emit_turn_limit_failure=True)
    child_executor = HarnessProgramStudyHarborExecutor()
    spec_path = tmp_path / "adaptive-cycle-spec.json"
    spec_path.write_text(json.dumps(spec.model_dump(mode="json")), encoding="utf-8")

    drifted_transfer_instruction = fixture_runtime.tasks_root / target_tasks[0] / "instruction.md"
    original_transfer_instruction = drifted_transfer_instruction.read_text(encoding="utf-8")
    drifted_transfer_instruction.write_text(
        original_transfer_instruction + "Post-preregistration drift.\n",
        encoding="utf-8",
    )
    blocked_source_executor = HarnessProgramStudyHarborExecutor()
    try:
        with pytest.raises(ValueError, match="transfer applicability changed after preregistration"):
            run_cli(
                [
                    "--spec",
                    str(spec_path),
                    "--project-root",
                    str(fixture_runtime.tasks_root.parent),
                    "--repo-root",
                    str(fixture_runtime.tasks_root.parent),
                    "--tasks-root",
                    str(fixture_runtime.tasks_root),
                    "--ledger-root",
                    str(tmp_path / "blocked-cycle-ledger"),
                    "--jobs-root",
                    str(tmp_path / "blocked-cycle-jobs"),
                    "--artifacts-root",
                    str(tmp_path / "blocked-adaptive-cycle-artifacts"),
                ],
                executors=AdaptiveCycleExecutors(
                    source=blocked_source_executor,
                    repair=RewardByTurnsHarborExecutor(emit_turn_limit_failure=True),
                    child_calibration=HarnessProgramStudyHarborExecutor(),
                ),
            )
    finally:
        drifted_transfer_instruction.write_text(
            original_transfer_instruction,
            encoding="utf-8",
        )
    assert blocked_source_executor.calls == 0

    source_instruction = fixture_runtime.tasks_root / fixture_runtime.request.pairing.task_ids[0] / "instruction.md"
    original_source_instruction = source_instruction.read_text(encoding="utf-8")
    drift_after_source_executor = TaskDriftAfterSourceExecutor(
        source_instruction,
        expected_calls=6,
    )
    blocked_repair_executor = RewardByTurnsHarborExecutor(emit_turn_limit_failure=True)
    try:
        with pytest.raises(
            RepairLoopError,
            match="repair spec task/task-review snapshots drifted before execution",
        ):
            run_cli(
                [
                    "--spec",
                    str(spec_path),
                    "--project-root",
                    str(fixture_runtime.tasks_root.parent),
                    "--repo-root",
                    str(fixture_runtime.tasks_root.parent),
                    "--tasks-root",
                    str(fixture_runtime.tasks_root),
                    "--ledger-root",
                    str(tmp_path / "mid-cycle-drift-ledger"),
                    "--jobs-root",
                    str(tmp_path / "mid-cycle-drift-jobs"),
                    "--artifacts-root",
                    str(tmp_path / "mid-cycle-drift-artifacts"),
                ],
                executors=AdaptiveCycleExecutors(
                    source=drift_after_source_executor,
                    repair=blocked_repair_executor,
                    child_calibration=HarnessProgramStudyHarborExecutor(),
                ),
            )
    finally:
        source_instruction.write_text(
            original_source_instruction,
            encoding="utf-8",
        )
    assert drift_after_source_executor.completed_calls == 6
    assert blocked_repair_executor.calls == []

    result = run_cli(
        [
            "--spec",
            str(spec_path),
            "--project-root",
            str(fixture_runtime.tasks_root.parent),
            "--repo-root",
            str(fixture_runtime.tasks_root.parent),
            "--tasks-root",
            str(fixture_runtime.tasks_root),
            "--ledger-root",
            str(tmp_path / "cycle-ledger"),
            "--jobs-root",
            str(tmp_path / "cycle-jobs"),
            "--artifacts-root",
            str(tmp_path / "adaptive-cycle-artifacts"),
        ],
        executors=AdaptiveCycleExecutors(
            source=source_executor,
            repair=repair_executor,
            child_calibration=child_executor,
        ),
    )

    assert capsys.readouterr().out.splitlines() == [str(result.path), result.report.content_sha256]
    assert result.report.outcome is AdaptiveCycleOutcome.STOPPED
    assert result.report.terminal_stage is AdaptiveCycleTerminalStage.MOTIF_PROMOTION
    assert result.report.terminal_reason is AdaptiveCycleTerminalReason.MOTIF_NOT_REUSABLE
    assert result.report.final_status is MotifStatus.PROVISIONAL
    assert result.child_calibration is not None
    assert result.learning is not None
    assert result.report.child_calibration_report is not None
    assert result.report.source_stage_report.sha256 == _sha256_path(result.source_stage.path)
    assert result.report.child_calibration_report.sha256 == _sha256_path(result.child_calibration.path)
    assert result.report.final_archive_sha256 == result.learning.library.archive_sha256
    assert result.path.is_file()
    assert result.path.parent.name == result.report.content_sha256
    assert load_adaptive_cycle_report(result.path) == result.report
    assert source_executor.calls == 6
    assert repair_executor.calls == [(17, 1), (29, 1), (17, 2), (29, 2)]
    assert child_executor.calls == 6

    rejected_payload = spec.model_dump(mode="python", exclude={"content_sha256"})
    rejected_payload["repair_request"]["acceptance_policy"] = RepairAcceptancePolicy(
        minimum_mean_reward_delta=0.8,
        bootstrap_replicates=32,
    )
    rejected_spec = AdaptiveCycleSpec.model_validate(rejected_payload)
    rejected_spec_path = tmp_path / "adaptive-cycle-rejected-spec.json"
    rejected_spec_path.write_text(
        json.dumps(rejected_spec.model_dump(mode="json")),
        encoding="utf-8",
    )
    rejected_child_executor = HarnessProgramStudyHarborExecutor()

    rejected = run_cli(
        [
            "--spec",
            str(rejected_spec_path),
            "--project-root",
            str(fixture_runtime.tasks_root.parent),
            "--repo-root",
            str(fixture_runtime.tasks_root.parent),
            "--tasks-root",
            str(fixture_runtime.tasks_root),
            "--ledger-root",
            str(tmp_path / "rejected-cycle-ledger"),
            "--jobs-root",
            str(tmp_path / "rejected-cycle-jobs"),
            "--artifacts-root",
            str(tmp_path / "rejected-adaptive-cycle-artifacts"),
        ],
        executors=AdaptiveCycleExecutors(
            source=HarnessProgramStudyHarborExecutor(),
            repair=RewardByTurnsHarborExecutor(emit_turn_limit_failure=True),
            child_calibration=rejected_child_executor,
        ),
    )

    assert capsys.readouterr().out.splitlines() == [
        str(rejected.path),
        rejected.report.content_sha256,
    ]
    assert rejected.report.outcome is AdaptiveCycleOutcome.STOPPED
    assert rejected.report.terminal_stage is AdaptiveCycleTerminalStage.REPAIR
    assert rejected.report.terminal_reason is AdaptiveCycleTerminalReason.REPAIR_REJECTED
    assert rejected.report.final_archive_sha256 == input_library.archive_sha256
    assert rejected.repaired_candidate is None
    assert rejected.child_calibration is None
    assert rejected.learning is None
    assert rejected_child_executor.calls == 0
    assert load_adaptive_cycle_report(rejected.path) == rejected.report

    Path(result.report.motif_library.path).write_text("{}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="adaptive cycle artifact digest mismatch"):
        load_adaptive_cycle_report(result.path)


def _sha256_path(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_world_sidecar(task_dir: Path, *, label: str) -> None:
    (task_dir / "task-review.json").write_text(
        json.dumps(
            {
                "profile_id": f"aec.task-review.civil.{label}",
                "name": f"Adaptive cycle {label}",
                "task_unit": "generated-task-instance",
                "logic_profile": {
                    "closure_gates": [],
                    "agentic_review": {"required": True},
                },
                "operation_profile": {
                    "subset_axes": ["inputs"],
                    "difference_axes": ["method"],
                    "projection_axes": ["answer"],
                    "product_axes": ["discipline", "method"],
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
