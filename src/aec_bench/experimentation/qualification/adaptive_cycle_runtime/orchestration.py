# ABOUTME: Orchestrates fixed-K adaptive evidence evaluation through the motif authority boundary.
# ABOUTME: Executes each causal stage while preserving explicit early-stop report prefixes.

from __future__ import annotations

from pathlib import Path

from aec_bench.contracts.harness_kernel import canonical_content_sha256
from aec_bench.evolution.repair_lifecycle import RepairLoopStatus
from aec_bench.experimentation.governance.motifs import MotifStatus
from aec_bench.experimentation.qualification.adaptive_cycle_runtime.artifacts import (
    artifact_reference,
    write_cycle_report,
    write_json_artifact,
)
from aec_bench.experimentation.qualification.adaptive_cycle_runtime.contracts import (
    AdaptiveCycleExecutors,
    AdaptiveCycleOutcome,
    AdaptiveCycleReport,
    AdaptiveCycleResult,
    AdaptiveCycleSpec,
    AdaptiveCycleTerminalReason,
    AdaptiveCycleTerminalStage,
    repair_terminal_reason,
)
from aec_bench.experimentation.qualification.adaptive_cycle_runtime.factor_bindings import (
    task_snapshots_for_refs,
)
from aec_bench.experimentation.qualification.adaptive_cycle_runtime.materialization import (
    materialize_child_harness_program_request,
)
from aec_bench.experimentation.qualification.adaptive_cycle_runtime.preflight import (
    preflight_cycle_inputs,
)
from aec_bench.experimentation.qualification.adaptive_diagnosis import (
    diagnosis_function_for_configuration,
)
from aec_bench.experimentation.qualification.harness_program_study import (
    prepare_harness_program_study_spec,
    run_harness_program_study,
)
from aec_bench.experimentation.qualification.motif_learning import (
    learn_and_promote_motif,
    write_motif_audit_report,
)
from aec_bench.experimentation.qualification.repair_runtime import (
    RepairEvidenceUsePolicy,
    RepairRuntime,
    RepairTerminalRecord,
)
from aec_bench.harness.harbor_workflow import SynchronousHarborWorkflow
from aec_bench.harness.kernel_catalogue import KernelRuntimeRegistry


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
    )


def _run_adaptive_cycle(
    *,
    spec: AdaptiveCycleSpec,
    registry: KernelRuntimeRegistry,
    workflow: SynchronousHarborWorkflow,
    artifacts_root: Path,
    executors: AdaptiveCycleExecutors | None,
) -> AdaptiveCycleResult:
    """Execute fixed-K evidence stages without granting protected motif status."""

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

    source_stage = run_harness_program_study(
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
                kind="harness-program-study-report",
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

    child_request = materialize_child_harness_program_request(
        source.child_calibration,
        repaired_candidate,
    )
    child_spec = prepare_harness_program_study_spec(
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
    child_calibration = run_harness_program_study(
        spec=child_spec,
        registry=registry,
        workflow=workflow,
        artifacts_root=root / "child-calibration",
        executor=selected_executors.child_calibration,
    )
    learning = learn_and_promote_motif(
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
                kind="harness-program-study-report",
            ),
            repair_terminal=repair.terminal.reference,
            repaired_candidate=repaired_candidate_reference,
            child_calibration_report=artifact_reference(
                child_calibration.path,
                kind="harness-program-study-report",
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
            report=report,
            path=path,
        )

    raise RuntimeError("adaptive cycle reached reusable status without governed qualification")
