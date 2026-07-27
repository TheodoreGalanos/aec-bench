# ABOUTME: Prepares and runs preregistered fixed-K factorial experiments through Harbor.
# ABOUTME: Builds exact candidate and trial evidence before publishing a verified report.

from __future__ import annotations

from pathlib import Path
from statistics import fmean

from aec_bench.contracts.harness_kernel import canonical_content_sha256
from aec_bench.contracts.trial_record import ArtifactReference
from aec_bench.harness.harbor_dispatch import HarborCommandExecutor
from aec_bench.harness.harbor_workflow import SynchronousHarborWorkflow
from aec_bench.meta_harness.applicability import profile_task_applicability
from aec_bench.meta_harness.factorial_candidates import (
    FactorialCandidateFactoryRequest,
    MaterializedFactorialCandidate,
    MaterializedFactorialCandidateSet,
    materialize_factorial_candidates,
)
from aec_bench.meta_harness.factorial_plan import FactorialStudyManifest
from aec_bench.meta_harness.factorial_study import FactorialStudyExecution, execute_factorial_study
from aec_bench.meta_harness.kernel_catalogue import KernelRuntimeRegistry

from .artifact_io import _sha256_path
from .contracts import (
    FactorialExperimentCandidateSetEvidence,
    FactorialExperimentCellEvidence,
    FactorialExperimentReport,
    FactorialExperimentRunResult,
    FactorialExperimentSpec,
    FactorialExperimentSplit,
    FactorialExperimentTrialEvidence,
)
from .persistence import _write_report, _write_spec_artifact
from .verification import _is_valid, verify_factorial_experiment_report


def prepare_factorial_experiment_spec(
    *,
    candidate_requests: tuple[FactorialCandidateFactoryRequest, ...],
    registry: KernelRuntimeRegistry,
    tasks_root: Path,
    policy_id: str,
    randomization_seed: int,
    harness_generator_sha256: str,
    program_generator_sha256: str,
    split: FactorialExperimentSplit,
    confidence_level: float = 0.95,
    bootstrap_replicates: int = 2_000,
    bootstrap_seed: int = 42,
) -> FactorialExperimentSpec:
    """Compile task snapshots without execution and freeze the exact FactorialStudyManifest."""
    requests = tuple(sorted(candidate_requests, key=lambda request: request.world_id))
    if not requests:
        raise ValueError("stage-zero requires at least one candidate factory request")
    applicability = profile_task_applicability(
        task_refs=tuple(sorted({task_ref for request in requests for task_ref in request.task_refs})),
        tasks_root=tasks_root,
        registry=registry,
    )
    materialized = tuple(
        materialize_factorial_candidates(request, registry=registry, tasks_root=tasks_root) for request in requests
    )
    experiment_ids = {request.experiment_id for request in requests}
    repetitions = {request.repetitions for request in requests}
    if len(experiment_ids) != 1 or len(repetitions) != 1:
        raise ValueError("stage-zero candidate requests must share one experiment and repetition count")
    manifest = FactorialStudyManifest(
        experiment_id=next(iter(experiment_ids)),
        randomization_seed=randomization_seed,
        repetitions=next(iter(repetitions)),
        candidate_sets=tuple(candidate.references for candidate in materialized),
    )
    return FactorialExperimentSpec(
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


def run_factorial_experiment(
    *,
    spec: FactorialExperimentSpec,
    registry: KernelRuntimeRegistry,
    workflow: SynchronousHarborWorkflow,
    artifacts_root: Path,
    executor: HarborCommandExecutor | None = None,
) -> FactorialExperimentRunResult:
    """Run a preregistered candidate search; the default executor is the real Harbor subprocess path."""
    source = FactorialExperimentSpec.model_validate(spec.model_dump(mode="python"))
    if any(request.kernel_ref != registry.manifest.ref for request in source.candidate_requests):
        raise ValueError("stage-zero spec does not target the installed fixed kernel")
    current_applicability = profile_task_applicability(
        task_refs=tuple(sorted({task_ref for request in source.candidate_requests for task_ref in request.task_refs})),
        tasks_root=workflow.tasks_root,
        registry=registry,
    )
    if current_applicability != source.applicability:
        raise ValueError("stage-zero applicability changed after preregistration")
    materialized = tuple(
        materialize_factorial_candidates(request, registry=registry, tasks_root=workflow.tasks_root)
        for request in source.candidate_requests
    )
    actual_references = tuple(candidate.references for candidate in materialized)
    if actual_references != source.study_manifest.candidate_sets:
        raise ValueError("materialized task inputs do not match preregistered candidate references")

    spec_artifact = _write_spec_artifact(source, artifacts_root=artifacts_root)
    execution = execute_factorial_study(
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
    verify_factorial_experiment_report(report)
    return FactorialExperimentRunResult(report=report, path=path)


def _build_report(
    *,
    spec: FactorialExperimentSpec,
    spec_artifact: ArtifactReference,
    materialized: tuple[MaterializedFactorialCandidateSet, ...],
    execution: FactorialStudyExecution,
    registry: KernelRuntimeRegistry,
) -> FactorialExperimentReport:
    trial_evidence = tuple(_trial_evidence(item) for item in execution.trial_executions)
    if any(not item.token_evidence_complete or not item.cost_evidence_complete for item in trial_evidence):
        raise ValueError("stage-zero requires complete token and cost evidence")
    candidate_evidence = tuple(
        _candidate_set_evidence(candidate_set, execution=execution) for candidate_set in materialized
    )
    records = tuple(record for trial in execution.trial_executions for record in trial.records)
    world_lineages = tuple(
        sorted(
            {
                provenance.world_package_sha256
                for record in records
                if (provenance := record.meta_harness_provenance) is not None
            }
        )
    )
    valid_records = sum(_is_valid(record) for record in records)
    return FactorialExperimentReport(
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
        analysis_sha256=canonical_content_sha256(execution.analysis.model_dump(mode="json")),
        world_lineage_ids=world_lineages,
        trial_count=len(trial_evidence),
        validity_rate=valid_records / len(records),
        observed_tokens=sum(item.observed_tokens for item in trial_evidence),
        token_evidence_complete=True,
        estimated_cost_usd=sum(float(item.estimated_cost_usd) for item in trial_evidence),
        cost_evidence_complete=True,
    )


def _candidate_set_evidence(
    candidate_set: MaterializedFactorialCandidateSet,
    *,
    execution: FactorialStudyExecution,
) -> FactorialExperimentCandidateSetEvidence:
    cells = tuple(_candidate_cell_evidence(candidate, execution=execution) for candidate in candidate_set.candidates)
    return FactorialExperimentCandidateSetEvidence(
        world_id=candidate_set.request.world_id,
        request=candidate_set.request,
        task_snapshots=candidate_set.candidates[0].bundle.task_snapshots,
        cells=cells,
    )


def _candidate_cell_evidence(
    candidate: MaterializedFactorialCandidate,
    *,
    execution: FactorialStudyExecution,
) -> FactorialExperimentCellEvidence:
    matching = {
        trial.execution.candidate_manifest.reference.sha256: trial.execution.candidate_manifest.reference
        for trial in execution.trial_executions
        if trial.candidate_reference == candidate.reference
    }
    if len(matching) != 1:
        raise ValueError("stage-zero candidate does not have exactly one stable candidate manifest")
    return FactorialExperimentCellEvidence(
        cell=candidate.cell,
        candidate_reference=candidate.reference,
        bundle_sha256=candidate.bundle.content_sha256,
        compiled_harness_sha256=candidate.bundle.harness.content_sha256,
        compiled_program_sha256=candidate.bundle.program.content_sha256,
        candidate_manifest=next(iter(matching.values())),
    )


def _trial_evidence(execution: object) -> FactorialExperimentTrialEvidence:
    from aec_bench.meta_harness.factorial_study import FactorialTrialExecution

    if not isinstance(execution, FactorialTrialExecution):
        raise TypeError("stage-zero requires FactorialTrialExecution evidence")
    paths = tuple(
        path for invocation in execution.execution.harbor_invocations for path in invocation.imported_trial_paths
    )
    if len(paths) != len(execution.records):
        raise ValueError("stage-zero TrialRecord paths do not match imported records")
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
        raise ValueError("stage-zero requires complete verifier evidence")
    token_complete = all(
        record.cost is not None and record.cost.tokens_in is not None and record.cost.tokens_out is not None
        for record in records
    )
    cost_complete = all(record.cost is not None and record.cost.estimated_cost_usd is not None for record in records)
    if not token_complete or not cost_complete:
        raise ValueError("stage-zero requires complete token and cost evidence")
    return FactorialExperimentTrialEvidence(
        trial=execution.trial,
        execution_seed=execution.execution_seed,
        candidate_reference=execution.candidate_reference,
        bundle_sha256=execution.execution.candidate_manifest.path.parent.name,
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
