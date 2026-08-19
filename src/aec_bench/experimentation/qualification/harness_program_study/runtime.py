# ABOUTME: Prepares and runs preregistered fixed-K harness-program studies through Harbor.
# ABOUTME: Builds exact candidate and trial evidence before publishing a verified report.

from __future__ import annotations

from pathlib import Path
from statistics import fmean

from aec_bench.contracts.harness_kernel import canonical_json_sha256
from aec_bench.contracts.trial_record import ArtifactReference
from aec_bench.experimentation.governance.applicability import profile_task_applicability
from aec_bench.experimentation.qualification.harness_program_study.candidates import (
    HarnessProgramCandidateRequest,
    MaterializedHarnessProgramCandidate,
    MaterializedHarnessProgramCandidateSet,
    materialize_harness_program_candidates,
)
from aec_bench.experimentation.qualification.harness_program_study.execution import (
    HarnessProgramStudyExecution,
    execute_harness_program_study,
)
from aec_bench.experimentation.qualification.harness_program_study.plan import HarnessProgramStudyManifest
from aec_bench.harness.harbor_dispatch import HarborCommandExecutor
from aec_bench.harness.harbor_workflow import SynchronousHarborWorkflow
from aec_bench.harness.kernel_catalogue import KernelRuntimeRegistry

from .artifact_io import _sha256_path
from .contracts import (
    HarnessProgramStudyCandidateSetEvidence,
    HarnessProgramStudyCellEvidence,
    HarnessProgramStudyReport,
    HarnessProgramStudyRunResult,
    HarnessProgramStudySpec,
    HarnessProgramStudySplit,
    HarnessProgramStudyTrialEvidence,
)
from .persistence import _write_report, _write_spec_artifact
from .verification import _is_valid, verify_harness_program_study_report


def prepare_harness_program_study_spec(
    *,
    candidate_requests: tuple[HarnessProgramCandidateRequest, ...],
    registry: KernelRuntimeRegistry,
    tasks_root: Path,
    policy_id: str,
    randomization_seed: int,
    harness_generator_sha256: str,
    program_generator_sha256: str,
    split: HarnessProgramStudySplit,
    confidence_level: float = 0.95,
    bootstrap_replicates: int = 2_000,
    bootstrap_seed: int = 42,
) -> HarnessProgramStudySpec:
    """Compile task snapshots without execution and freeze the exact HarnessProgramStudyManifest."""
    requests = tuple(sorted(candidate_requests, key=lambda request: request.task_set_id))
    if not requests:
        raise ValueError("harness-program-study requires at least one candidate factory request")
    applicability = profile_task_applicability(
        task_refs=tuple(sorted({task_ref for request in requests for task_ref in request.task_refs})),
        tasks_root=tasks_root,
        registry=registry,
    )
    materialized = tuple(
        materialize_harness_program_candidates(request, registry=registry, tasks_root=tasks_root)
        for request in requests
    )
    experiment_ids = {request.experiment_id for request in requests}
    repetitions = {request.repetitions for request in requests}
    if len(experiment_ids) != 1 or len(repetitions) != 1:
        raise ValueError("harness-program-study candidate requests must share one experiment and repetition count")
    manifest = HarnessProgramStudyManifest(
        experiment_id=next(iter(experiment_ids)),
        randomization_seed=randomization_seed,
        repetitions=next(iter(repetitions)),
        candidate_sets=tuple(candidate.references for candidate in materialized),
    )
    return HarnessProgramStudySpec(
        policy_id=policy_id,
        split=split,
        harness_generator_sha256=harness_generator_sha256,
        program_generator_sha256=program_generator_sha256,
        candidate_requests=requests,
        applicability=applicability,
        study_manifest=manifest,
        confidence_level=confidence_level,
        bootstrap_replicates=bootstrap_replicates,
        bootstrap_seed=bootstrap_seed,
    )


def run_harness_program_study(
    *,
    spec: HarnessProgramStudySpec,
    registry: KernelRuntimeRegistry,
    workflow: SynchronousHarborWorkflow,
    artifacts_root: Path,
    executor: HarborCommandExecutor | None = None,
) -> HarnessProgramStudyRunResult:
    """Run a preregistered candidate search; the default executor is the real Harbor subprocess path."""
    source = HarnessProgramStudySpec.model_validate(spec.model_dump(mode="python"))
    if any(request.kernel_ref != registry.manifest.ref for request in source.candidate_requests):
        raise ValueError("harness-program-study spec does not target the installed fixed kernel")
    current_applicability = profile_task_applicability(
        task_refs=tuple(sorted({task_ref for request in source.candidate_requests for task_ref in request.task_refs})),
        tasks_root=workflow.tasks_root,
        registry=registry,
    )
    if current_applicability != source.applicability:
        raise ValueError("harness-program-study applicability changed after preregistration")
    materialized = tuple(
        materialize_harness_program_candidates(request, registry=registry, tasks_root=workflow.tasks_root)
        for request in source.candidate_requests
    )
    actual_references = tuple(candidate.references for candidate in materialized)
    if actual_references != source.study_manifest.candidate_sets:
        raise ValueError("materialized task inputs do not match preregistered candidate references")

    spec_artifact = _write_spec_artifact(source, artifacts_root=artifacts_root)
    execution = execute_harness_program_study(
        candidates=materialized,
        manifest=source.study_manifest,
        registry=registry,
        workflow=workflow,
        artifacts_root=artifacts_root,
        policy_id=source.policy_id,
        harness_generator_sha256=source.harness_generator_sha256,
        program_generator_sha256=source.program_generator_sha256,
        split=source.split,
        executor=executor,
        confidence_level=source.confidence_level,
        bootstrap_replicates=source.bootstrap_replicates,
        bootstrap_seed=source.bootstrap_seed,
    )
    report = _build_report(
        spec=source,
        spec_artifact=spec_artifact,
        materialized=materialized,
        execution=execution,
        registry=registry,
    )
    path = _write_report(report, artifacts_root=artifacts_root)
    verify_harness_program_study_report(report)
    return HarnessProgramStudyRunResult(report=report, path=path)


def _build_report(
    *,
    spec: HarnessProgramStudySpec,
    spec_artifact: ArtifactReference,
    materialized: tuple[MaterializedHarnessProgramCandidateSet, ...],
    execution: HarnessProgramStudyExecution,
    registry: KernelRuntimeRegistry,
) -> HarnessProgramStudyReport:
    trial_evidence = tuple(_trial_evidence(item) for item in execution.trial_executions)
    if any(not item.token_evidence_complete or not item.cost_evidence_complete for item in trial_evidence):
        raise ValueError("harness-program-study requires complete token and cost evidence")
    candidate_evidence = tuple(
        _candidate_set_evidence(candidate_set, execution=execution) for candidate_set in materialized
    )
    records = tuple(record for trial in execution.trial_executions for record in trial.records)
    review_lineages = spec.applicability.review_lineage_ids
    valid_records = sum(_is_valid(record) for record in records)
    return HarnessProgramStudyReport(
        spec_sha256=spec.content_sha256,
        spec_artifact=spec_artifact,
        kernel_ref=registry.manifest.ref,
        applicability=spec.applicability,
        split=spec.split,
        manifest=execution.manifest,
        plan=execution.plan,
        plan_artifact=execution.plan_artifact.reference,
        candidates=candidate_evidence,
        trials=trial_evidence,
        analysis=execution.analysis,
        analysis_sha256=canonical_json_sha256(execution.analysis.model_dump(mode="json")),
        review_lineage_ids=review_lineages,
        trial_count=len(trial_evidence),
        validity_rate=valid_records / len(records),
        observed_tokens=sum(item.observed_tokens for item in trial_evidence),
        token_evidence_complete=True,
        estimated_cost_usd=sum(float(item.estimated_cost_usd) for item in trial_evidence),
        cost_evidence_complete=True,
    )


def _candidate_set_evidence(
    candidate_set: MaterializedHarnessProgramCandidateSet,
    *,
    execution: HarnessProgramStudyExecution,
) -> HarnessProgramStudyCandidateSetEvidence:
    cells = tuple(_candidate_cell_evidence(candidate, execution=execution) for candidate in candidate_set.candidates)
    return HarnessProgramStudyCandidateSetEvidence(
        task_set_id=candidate_set.request.task_set_id,
        request=candidate_set.request,
        task_snapshots=candidate_set.candidates[0].bundle.task_snapshots,
        cells=cells,
    )


def _candidate_cell_evidence(
    candidate: MaterializedHarnessProgramCandidate,
    *,
    execution: HarnessProgramStudyExecution,
) -> HarnessProgramStudyCellEvidence:
    return HarnessProgramStudyCellEvidence(
        cell=candidate.cell,
        candidate_reference=candidate.reference,
        bundle_id=candidate.bundle.run_manifest.run_id,
        compiled_harness_ref=candidate.bundle.harness.ref,
        compiled_program_ref=candidate.bundle.execution_program.ref,
    )


def _trial_evidence(execution: object) -> HarnessProgramStudyTrialEvidence:
    from aec_bench.experimentation.qualification.harness_program_study.execution import HarnessProgramTrialExecution

    if not isinstance(execution, HarnessProgramTrialExecution):
        raise TypeError("harness-program-study requires HarnessProgramTrialExecution evidence")
    paths = tuple(
        path for invocation in execution.execution.harbor_invocations for path in invocation.imported_trial_paths
    )
    if len(paths) != len(execution.records):
        raise ValueError("harness-program-study TrialRecord paths do not match imported records")
    artifacts = tuple(
        ArtifactReference(
            kind="trial-record",
            path=str(path.resolve()),
            sha256=_sha256_path(path),
            media_type="application/json",
        )
        for path in paths
    )
    records = execution.records
    if any(not record.evaluation.validity.verifier_completed for record in records):
        raise ValueError("harness-program-study requires complete verifier evidence")
    token_complete = all(
        record.cost is not None and record.cost.tokens_in is not None and record.cost.tokens_out is not None
        for record in records
    )
    cost_complete = all(record.cost is not None and record.cost.estimated_cost_usd is not None for record in records)
    if not token_complete or not cost_complete:
        raise ValueError("harness-program-study requires complete token and cost evidence")
    return HarnessProgramStudyTrialEvidence(
        trial=execution.trial,
        execution_seed=execution.execution_seed,
        candidate_reference=execution.candidate_reference,
        bundle_id=execution.bundle_id,
        trial_record_ids=tuple(record.trial_id for record in records),
        trial_records=artifacts,
        budget=execution.execution.budget,
        mean_reward=fmean(record.evaluation.reward for record in records),
        validity_rate=sum(_is_valid(record) for record in records) / len(records),
        observed_tokens=sum(
            (record.cost.tokens_in or 0) + (record.cost.tokens_out or 0) for record in records if record.cost
        ),
        token_evidence_complete=True,
        estimated_cost_usd=sum(float(record.cost.estimated_cost_usd or 0.0) for record in records if record.cost),
        cost_evidence_complete=True,
    )
