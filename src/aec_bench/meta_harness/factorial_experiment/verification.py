# ABOUTME: Verifies factorial reports against bound specs, plans, candidates, and TrialRecords.
# ABOUTME: Recomputes analysis and resource aggregates so persisted conclusions fail closed on drift.

from __future__ import annotations

from pathlib import Path
from statistics import fmean

from aec_bench.contracts.run_bundle import RunBundle
from aec_bench.contracts.trial_record import ArtifactReference, TrialRecord
from aec_bench.meta_harness.factorial_analysis import FactorialOutcome, analyse_factorial

from .artifact_io import _load_path_bytes, _read_json_object, _verify_artifact
from .contracts import (
    FactorialExperimentReport,
    FactorialExperimentSpec,
    FactorialExperimentTrialEvidence,
)


def verify_factorial_experiment_report(report: FactorialExperimentReport) -> None:
    """Fail closed unless report conclusions exactly derive from its bound TrialRecords."""
    validated = FactorialExperimentReport.model_validate(report.model_dump(mode="python"))
    spec = _load_bound_experiment_spec(validated)
    _verify_bound_plan_artifact(validated)
    _verify_bound_candidate_artifacts(validated)
    outcomes, records = _load_bound_trial_evidence(validated)
    recomputed_analysis = analyse_factorial(
        validated.plan,
        outcomes,
        confidence_level=spec.confidence_level,
        bootstrap_replicates=spec.bootstrap_replicates,
        bootstrap_seed=spec.bootstrap_seed,
    )
    if recomputed_analysis != validated.analysis:
        raise ValueError(
            "stage-zero report analysis does not match its derived evidence",
        )
    _verify_derived_report_aggregates(validated, records=records)


def _load_bound_experiment_spec(
    report: FactorialExperimentReport,
) -> FactorialExperimentSpec:
    artifact = report.spec_artifact
    if artifact.kind != "stage-zero-spec":
        raise ValueError("stage-zero report has an invalid spec artifact kind")
    _verify_artifact(artifact)
    spec_payload = _read_json_object(
        Path(artifact.path),
        label="stage-zero spec",
    )
    try:
        spec = FactorialExperimentSpec.model_validate(spec_payload.get("spec"))
    except Exception as error:
        raise ValueError(
            "stage-zero spec artifact does not contain a valid strict spec",
        ) from error
    if (
        spec.content_sha256 != report.spec_sha256
        or spec.split != report.split
        or spec.study_manifest != report.manifest
        or spec.applicability != report.applicability
        or spec.candidate_requests != tuple(candidate.request for candidate in report.candidates)
    ):
        raise ValueError(
            "stage-zero report does not bind its preregistered spec",
        )
    return spec


def _verify_bound_plan_artifact(
    report: FactorialExperimentReport,
) -> None:
    artifact = report.plan_artifact
    if artifact.kind != "factorial-plan":
        raise ValueError(
            "stage-zero report has an invalid factorial plan artifact kind",
        )
    _verify_artifact(artifact)
    payload = _read_json_object(
        Path(artifact.path),
        label="factorial plan",
    )
    if payload.get("plan") != report.plan.model_dump(mode="json"):
        raise ValueError(
            "stage-zero report does not bind its factorial plan artifact",
        )
    if payload.get("execution_seeds") != list(
        report.candidates[0].request.seeds,
    ):
        raise ValueError(
            "stage-zero report plan seed schedule does not match its source factors",
        )


def _verify_bound_candidate_artifacts(
    report: FactorialExperimentReport,
) -> None:
    for candidate_set in report.candidates:
        for cell in candidate_set.cells:
            artifact = cell.candidate_manifest
            if artifact.kind != "candidate-manifest":
                raise ValueError(
                    "stage-zero report has an invalid candidate artifact kind",
                )
            _verify_artifact(artifact)
            payload = _read_json_object(
                Path(artifact.path),
                label="candidate manifest",
            )
            bundle = RunBundle.model_validate(payload.get("bundle"))
            if bundle.content_sha256 != cell.bundle_sha256:
                raise ValueError(
                    "candidate manifest bundle identity does not match stage-zero report",
                )


def _load_bound_trial_evidence(
    report: FactorialExperimentReport,
) -> tuple[list[FactorialOutcome], tuple[TrialRecord, ...]]:
    requests_by_world = {candidate.world_id: candidate.request for candidate in report.candidates}
    outcomes: list[FactorialOutcome] = []
    all_records: list[TrialRecord] = []
    for trial in report.trials:
        records = _load_bound_trial_records(report, trial=trial)
        request = requests_by_world[trial.trial.world_id]
        if {record.task.task_id for record in records} != set(
            request.task_refs,
        ):
            raise ValueError(
                "stage-zero TrialRecords do not exactly cover their source tasks",
            )
        outcomes.append(
            _verify_derived_trial_evidence(trial, records=records),
        )
        all_records.extend(records)
    return outcomes, tuple(all_records)


def _load_bound_trial_records(
    report: FactorialExperimentReport,
    *,
    trial: FactorialExperimentTrialEvidence,
) -> tuple[TrialRecord, ...]:
    records = tuple(
        _load_trial_record(artifact, trial_id=trial_id)
        for artifact, trial_id in zip(
            trial.trial_records,
            trial.trial_record_ids,
            strict=True,
        )
    )
    for record in records:
        _validate_trial_record_lineage(report, trial=trial, record=record)
    return records


def _load_trial_record(
    artifact: ArtifactReference,
    *,
    trial_id: str,
) -> TrialRecord:
    if artifact.kind != "trial-record":
        raise ValueError(
            "stage-zero report has an invalid TrialRecord artifact kind",
        )
    _verify_artifact(artifact)
    try:
        record = TrialRecord.model_validate_json(
            _load_path_bytes(
                Path(artifact.path),
                label="stage-zero TrialRecord artifact",
            ),
        )
    except Exception as error:
        raise ValueError(
            f"invalid stage-zero TrialRecord artifact: {artifact.path}",
        ) from error
    if record.trial_id != trial_id:
        raise ValueError(
            "stage-zero TrialRecord id does not match report evidence",
        )
    return record


def _validate_trial_record_lineage(
    report: FactorialExperimentReport,
    *,
    trial: FactorialExperimentTrialEvidence,
    record: TrialRecord,
) -> None:
    provenance = record.meta_harness_provenance
    if (
        provenance is None
        or provenance.run_id != trial.trial.trial_id
        or provenance.execution_seed != trial.execution_seed
        or provenance.bundle_sha256 != trial.bundle_sha256
        or provenance.factorial_cell != trial.trial.cell.value
        or provenance.paired_block_id != trial.trial.block_id
        or provenance.factorial_plan != report.plan_artifact
        or provenance.kernel_sha256 != report.kernel_ref.content_sha256
        or provenance.harness_sha256 != trial.candidate_reference.harness_sha256
    ):
        raise ValueError(
            "stage-zero TrialRecord lineage does not match report evidence",
        )


def _verify_derived_trial_evidence(
    trial: FactorialExperimentTrialEvidence,
    *,
    records: tuple[TrialRecord, ...],
) -> FactorialOutcome:
    if any(not record.evaluation.validity.verifier_completed for record in records):
        raise ValueError("stage-zero report references incomplete verifier evidence")
    valid_records = sum(_is_valid(record) for record in records)
    token_evidence_complete = all(
        record.cost is not None and record.cost.tokens_in is not None and record.cost.tokens_out is not None
        for record in records
    )
    cost_evidence_complete = all(
        record.cost is not None and record.cost.estimated_cost_usd is not None for record in records
    )
    observed_tokens = sum(
        (record.cost.tokens_in or 0) + (record.cost.tokens_out or 0) for record in records if record.cost is not None
    )
    estimated_cost = sum(float(record.cost.estimated_cost_usd or 0.0) for record in records if record.cost is not None)
    observed_trial_seconds = sum(float(record.timing.total_seconds) for record in records)
    mean_reward = fmean(record.evaluation.reward for record in records)
    validity_rate = valid_records / len(records)

    if (
        trial.mean_reward != mean_reward
        or trial.validity_rate != validity_rate
        or trial.observed_tokens != observed_tokens
        or trial.token_evidence_complete is not token_evidence_complete
        or float(trial.estimated_cost_usd) != estimated_cost
        or trial.cost_evidence_complete is not cost_evidence_complete
        or trial.budget.imported_trials != len(records)
        or trial.budget.observed_tokens != observed_tokens
        or trial.budget.token_evidence_complete is not token_evidence_complete
        or float(trial.budget.observed_cost_usd) != estimated_cost
        or trial.budget.cost_evidence_complete is not cost_evidence_complete
        or float(trial.budget.observed_trial_seconds) != observed_trial_seconds
    ):
        raise ValueError("stage-zero trial summary does not match its derived evidence")
    if not token_evidence_complete or not cost_evidence_complete:
        raise ValueError("stage-zero report references incomplete TrialRecord evidence")
    return FactorialOutcome(trial_id=trial.trial.trial_id, value=mean_reward)


def _verify_derived_report_aggregates(
    report: FactorialExperimentReport,
    *,
    records: tuple[TrialRecord, ...],
) -> None:
    valid_records = sum(_is_valid(record) for record in records)
    token_evidence_complete = all(
        record.cost is not None and record.cost.tokens_in is not None and record.cost.tokens_out is not None
        for record in records
    )
    cost_evidence_complete = all(
        record.cost is not None and record.cost.estimated_cost_usd is not None for record in records
    )
    observed_tokens = sum(
        (record.cost.tokens_in or 0) + (record.cost.tokens_out or 0) for record in records if record.cost is not None
    )
    estimated_cost = sum(float(trial.estimated_cost_usd) for trial in report.trials)
    world_lineage_ids = tuple(
        sorted(
            {
                provenance.world_package_sha256
                for record in records
                if (provenance := record.meta_harness_provenance) is not None
            }
        )
    )
    if (
        report.world_lineage_ids != world_lineage_ids
        or report.trial_count != len(report.trials)
        or report.validity_rate != valid_records / len(records)
        or report.observed_tokens != observed_tokens
        or report.token_evidence_complete is not token_evidence_complete
        or float(report.estimated_cost_usd) != estimated_cost
        or report.cost_evidence_complete is not cost_evidence_complete
    ):
        raise ValueError("stage-zero report aggregates do not match their derived evidence")


def _is_valid(record: TrialRecord) -> bool:
    validity = record.evaluation.validity
    return validity.verifier_completed and validity.output_parseable and validity.schema_valid
