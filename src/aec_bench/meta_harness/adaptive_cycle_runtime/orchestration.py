# ABOUTME: Orchestrates fixed-K adaptive evidence evaluation through the motif authority boundary.
# ABOUTME: Executes each causal stage while preserving explicit early-stop report prefixes.

from __future__ import annotations

from pathlib import Path

from aec_bench.contracts.harness_kernel import canonical_content_sha256
from aec_bench.evolution.repair_loop import RepairLoopStatus
from aec_bench.harness.harbor_workflow import SynchronousHarborWorkflow
from aec_bench.meta_harness.adaptive_cycle_runtime.artifacts import (
    artifact_reference,
    write_cycle_report,
    write_json_artifact,
)
from aec_bench.meta_harness.adaptive_cycle_runtime.contracts import (
    AdaptiveCycleExecutors,
    AdaptiveCycleOutcome,
    AdaptiveCycleReport,
    AdaptiveCycleResult,
    AdaptiveCycleSpec,
    AdaptiveCycleTerminalReason,
    AdaptiveCycleTerminalStage,
    _AdaptiveCycleLifecycle,
    repair_terminal_reason,
)
from aec_bench.meta_harness.adaptive_cycle_runtime.factor_bindings import (
    align_instantiation_runtime_resource_budget,
    task_snapshots_for_refs,
)
from aec_bench.meta_harness.adaptive_cycle_runtime.materialization import (
    materialize_child_factorial_request,
)
from aec_bench.meta_harness.adaptive_cycle_runtime.preflight import (
    preflight_cycle_inputs,
)
from aec_bench.meta_harness.adaptive_diagnosis import (
    diagnosis_function_for_configuration,
)
from aec_bench.meta_harness.factorial_experiment import (
    prepare_factorial_experiment_spec,
    run_factorial_experiment,
)
from aec_bench.meta_harness.kernel_catalogue import KernelRuntimeRegistry
from aec_bench.meta_harness.motif_learning import (
    learn_and_promote_motif,
    learn_and_promote_motif_v1_compatibility,
    select_and_materialize_motif_v1_compatibility,
    write_motif_audit_report,
)
from aec_bench.meta_harness.motif_library import MotifStatus
from aec_bench.meta_harness.motif_transfer_runtime import (
    execute_motif_transfer_v1_compatibility,
)
from aec_bench.meta_harness.repair_runtime import (
    RepairEvidenceUsePolicy,
    RepairRuntime,
    RepairTerminalRecord,
)


def run_adaptive_cycle(
    *,
    spec: AdaptiveCycleSpec,
    registry: KernelRuntimeRegistry,
    workflow: SynchronousHarborWorkflow,
    artifacts_root: Path,
    executors: AdaptiveCycleExecutors | None = None,
) -> AdaptiveCycleResult:
    """Run evidence evaluation and stop before authority-bearing motif promotion."""

    return _run_adaptive_cycle(
        spec=spec,
        registry=registry,
        workflow=workflow,
        artifacts_root=artifacts_root,
        executors=executors,
        lifecycle=_AdaptiveCycleLifecycle.ACTIVE,
    )


def run_adaptive_cycle_v1_compatibility(
    *,
    spec: AdaptiveCycleSpec,
    registry: KernelRuntimeRegistry,
    workflow: SynchronousHarborWorkflow,
    artifacts_root: Path,
    executors: AdaptiveCycleExecutors | None = None,
) -> AdaptiveCycleResult:
    """Replay the historical v1 ungoverned learning, dispatch, and transfer lifecycle."""

    return _run_adaptive_cycle(
        spec=spec,
        registry=registry,
        workflow=workflow,
        artifacts_root=artifacts_root,
        executors=executors,
        lifecycle=_AdaptiveCycleLifecycle.V1_COMPATIBILITY,
    )


def _run_adaptive_cycle(
    *,
    spec: AdaptiveCycleSpec,
    registry: KernelRuntimeRegistry,
    workflow: SynchronousHarborWorkflow,
    artifacts_root: Path,
    executors: AdaptiveCycleExecutors | None,
    lifecycle: _AdaptiveCycleLifecycle,
) -> AdaptiveCycleResult:
    """Execute common fixed-K stages under one explicit lifecycle authority policy."""

    source = AdaptiveCycleSpec.model_validate(spec.model_dump(mode="python"))
    input_library = preflight_cycle_inputs(
        spec=source,
        registry=registry,
        tasks_root=workflow.tasks_root,
    )
    selected_executors = executors or AdaptiveCycleExecutors()
    root = Path(artifacts_root)
    spec_reference = write_json_artifact(
        source.model_dump(mode="json"),
        identity=source.content_sha256,
        root=root / "adaptive-cycle-specs",
        filename="adaptive-cycle-spec.json",
        kind="adaptive-cycle-spec",
    )

    source_stage = run_factorial_experiment(
        spec=source.source_stage,
        registry=registry,
        workflow=workflow,
        artifacts_root=root / "source-stage",
        executor=selected_executors.source,
    )
    repair_runtime = RepairRuntime(
        request=source.repair_request,
        parent=source.repair_parent,
        registry=registry,
        workflow=workflow,
        artifacts_root=root / "repair",
        policy_id=f"{source.child_calibration.policy_id}.repair",
        harness_generator_sha256=source.harness_generator_sha256,
        program_generator_sha256=source.program_generator_sha256,
        verifier_policy=source.repair_verifier_policy,
        evidence_use_policy=(RepairEvidenceUsePolicy.calibration_gated_adaptive_cycle()),
        diagnosis=diagnosis_function_for_configuration(source.diagnosis_rule),
        preregistered_task_snapshots=task_snapshots_for_refs(
            source.source_stage.applicability,
            task_refs=source.repair_request.pairing.task_ids,
        ),
        executor=selected_executors.repair,
    )
    repair = repair_runtime.execute()
    if repair.result.status is not RepairLoopStatus.ACCEPTED:
        report = AdaptiveCycleReport(
            outcome=AdaptiveCycleOutcome.STOPPED,
            terminal_stage=AdaptiveCycleTerminalStage.REPAIR,
            terminal_reason=repair_terminal_reason(repair.result.status),
            spec_sha256=source.content_sha256,
            spec_artifact=spec_reference,
            kernel_ref=registry.manifest.ref,
            input_motif_library=source.input_motif_library,
            source_stage_report=artifact_reference(
                source_stage.path,
                kind="stage-zero-report",
            ),
            repair_terminal=repair.terminal.reference,
            motif_library=source.input_motif_library.artifact,
            final_archive_sha256=input_library.archive_sha256,
        )
        path = write_cycle_report(report, root=root)
        return AdaptiveCycleResult(
            source_stage=source_stage,
            repair=repair,
            repaired_candidate=None,
            child_calibration=None,
            learning=None,
            transfer=None,
            report=report,
            path=path,
        )
    terminal = RepairTerminalRecord.model_validate_json(repair.terminal.path.read_text(encoding="utf-8"))
    if terminal.patch_proposal is None:
        raise ValueError("accepted adaptive repair is missing its typed patch proposal")
    repaired_candidate = repair_runtime.apply_patch(terminal.patch_proposal)
    repaired_candidate_reference = write_json_artifact(
        repaired_candidate.model_dump(mode="json"),
        identity=canonical_content_sha256(repaired_candidate.model_dump(mode="json")),
        root=root / "repair-candidates",
        filename="repair-candidate.json",
        kind="repair-candidate",
    )

    child_request = materialize_child_factorial_request(
        source.child_calibration,
        repaired_candidate,
    )
    child_spec = prepare_factorial_experiment_spec(
        candidate_requests=(child_request,),
        registry=registry,
        tasks_root=workflow.tasks_root,
        policy_id=source.child_calibration.policy_id,
        randomization_seed=source.child_calibration.randomization_seed,
        harness_generator_sha256=source.harness_generator_sha256,
        program_generator_sha256=source.program_generator_sha256,
        split="calibration",
        confidence_level=source.child_calibration.confidence_level,
        bootstrap_replicates=source.child_calibration.bootstrap_replicates,
        bootstrap_seed=source.child_calibration.bootstrap_seed,
    )
    if child_spec.applicability != source.child_calibration.applicability:
        raise ValueError("adaptive cycle child applicability drifted while materializing repaired factors")
    child_calibration = run_factorial_experiment(
        spec=child_spec,
        registry=registry,
        workflow=workflow,
        artifacts_root=root / "child-calibration",
        executor=selected_executors.child_calibration,
    )
    learning_function = (
        learn_and_promote_motif_v1_compatibility
        if lifecycle is _AdaptiveCycleLifecycle.V1_COMPATIBILITY
        else learn_and_promote_motif
    )
    learning = learning_function(
        source_stage_report=source_stage.report,
        child_calibration_report=child_calibration.report,
        repair_execution=repair,
        repaired_candidate=repaired_candidate,
        policy=source.promotion_policy,
        registry=registry,
        library=input_library,
    )
    learning_reference = write_motif_audit_report(
        learning.report,
        artifacts_root=root / "motif-reports",
    )
    learning_library_reference = write_json_artifact(
        learning.library.model_dump(mode="json"),
        identity=learning.library.archive_sha256,
        root=root / "motif-libraries",
        filename="motif-library.json",
        kind="motif-library",
    )
    if learning.motif.status is not MotifStatus.REUSABLE:
        report = AdaptiveCycleReport(
            outcome=AdaptiveCycleOutcome.STOPPED,
            terminal_stage=AdaptiveCycleTerminalStage.MOTIF_PROMOTION,
            terminal_reason=AdaptiveCycleTerminalReason.MOTIF_NOT_REUSABLE,
            spec_sha256=source.content_sha256,
            spec_artifact=spec_reference,
            kernel_ref=registry.manifest.ref,
            input_motif_library=source.input_motif_library,
            source_stage_report=artifact_reference(
                source_stage.path,
                kind="stage-zero-report",
            ),
            repair_terminal=repair.terminal.reference,
            repaired_candidate=repaired_candidate_reference,
            child_calibration_report=artifact_reference(
                child_calibration.path,
                kind="stage-zero-report",
            ),
            motif_learning_report=learning_reference,
            learning_motif_library=learning_library_reference,
            motif_library=learning_library_reference,
            learned_motif_sha256=learning.motif.motif_sha256,
            learning_archive_sha256=learning.library.archive_sha256,
            final_motif_sha256=learning.motif.motif_sha256,
            final_archive_sha256=learning.library.archive_sha256,
            final_status=learning.motif.status,
        )
        path = write_cycle_report(report, root=root)
        return AdaptiveCycleResult(
            source_stage=source_stage,
            repair=repair,
            repaired_candidate=repaired_candidate,
            child_calibration=child_calibration,
            learning=learning,
            transfer=None,
            report=report,
            path=path,
        )

    if lifecycle is not _AdaptiveCycleLifecycle.V1_COMPATIBILITY:
        raise RuntimeError("active adaptive cycle reached reusable status without governed qualification")
    transfer_plan = select_and_materialize_motif_v1_compatibility(
        library=learning.library,
        applicability=source.transfer.applicability,
        selection_split="calibration",
        request=align_instantiation_runtime_resource_budget(
            source.transfer.instantiation,
            repaired_candidate.harness_request.recipe,
        ),
    )
    transfer = execute_motif_transfer_v1_compatibility(
        frozen_library=learning.library,
        plan=transfer_plan,
        policy=source.promotion_policy,
        registry=registry,
        workflow=workflow,
        artifacts_root=root / "transfer",
        policy_id=source.transfer.policy_id,
        harness_generator_sha256=source.harness_generator_sha256,
        program_generator_sha256=source.program_generator_sha256,
        randomization_seed=source.transfer.randomization_seed,
        executor=selected_executors.transfer,
        confidence_level=source.transfer.confidence_level,
        bootstrap_replicates=source.transfer.bootstrap_replicates,
        bootstrap_seed=source.transfer.bootstrap_seed,
    )
    promotion_reference = write_motif_audit_report(
        transfer.finalization.report,
        artifacts_root=root / "motif-reports",
    )
    evaluation_reference = write_json_artifact(
        transfer.evaluation.model_dump(mode="json"),
        identity=transfer.evaluation.content_sha256,
        root=root / "transfer-evaluations",
        filename="motif-transfer-evaluation.json",
        kind="motif-transfer-evaluation",
    )
    library_reference = write_json_artifact(
        transfer.finalization.library.model_dump(mode="json"),
        identity=transfer.finalization.library.archive_sha256,
        root=root / "motif-libraries",
        filename="motif-library.json",
        kind="motif-library",
    )
    report = AdaptiveCycleReport(
        outcome=AdaptiveCycleOutcome.COMPLETED,
        terminal_stage=AdaptiveCycleTerminalStage.TRANSFER_PROMOTION,
        terminal_reason=(
            AdaptiveCycleTerminalReason.TRANSFER_VALIDATED
            if transfer.finalization.motif.status is MotifStatus.TRANSFER_VALIDATED
            else AdaptiveCycleTerminalReason.TRANSFER_GATE_REJECTED
        ),
        spec_sha256=source.content_sha256,
        spec_artifact=spec_reference,
        kernel_ref=registry.manifest.ref,
        input_motif_library=source.input_motif_library,
        source_stage_report=artifact_reference(
            source_stage.path,
            kind="stage-zero-report",
        ),
        repair_terminal=repair.terminal.reference,
        repaired_candidate=repaired_candidate_reference,
        child_calibration_report=artifact_reference(
            child_calibration.path,
            kind="stage-zero-report",
        ),
        motif_learning_report=learning_reference,
        learning_motif_library=learning_library_reference,
        transfer_evaluation_report=evaluation_reference,
        transfer_promotion_report=promotion_reference,
        motif_library=library_reference,
        learned_motif_sha256=learning.motif.motif_sha256,
        learning_archive_sha256=learning.library.archive_sha256,
        final_motif_sha256=transfer.finalization.motif.motif_sha256,
        final_archive_sha256=transfer.finalization.library.archive_sha256,
        final_status=transfer.finalization.motif.status,
    )
    report_path = write_cycle_report(report, root=root)
    return AdaptiveCycleResult(
        source_stage=source_stage,
        repair=repair,
        repaired_candidate=repaired_candidate,
        child_calibration=child_calibration,
        learning=learning,
        transfer=transfer,
        report=report,
        path=report_path,
    )
