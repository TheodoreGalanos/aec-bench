# ABOUTME: Runs real model agents through the delayed-evidence paired study.
# ABOUTME: Publishes usage, endpoint, and replay evidence for independent reload.

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any, Literal

from pydantic import NonNegativeInt, TypeAdapter, field_validator, model_validator

from aec_bench.adapters.base import AdapterFailureKind, AdapterRequest, AdapterResult
from aec_bench.contracts.harness_kernel import ContentAddressedModel, canonical_content_sha256, validate_sha256
from aec_bench.contracts.validators import NonEmptyStr
from aec_bench.experiments.retrieval_state_continuity.analysis import analyse_study
from aec_bench.experiments.retrieval_state_continuity.artifacts import (
    reload_and_verify_study_report,
)
from aec_bench.experiments.retrieval_state_continuity.contracts import (
    FailureKind,
    ObservationSource,
    PairIneligibilityReason,
    PlannedTrial,
    StudyManifest,
    StudyObservation,
    StudyPhase,
    StudyPlan,
    StudyReport,
    Treatment,
    TreatmentDelivery,
    TreatmentDeliveryStatus,
)
from aec_bench.experiments.retrieval_state_continuity.planning import (
    build_model_manifest,
    build_study_plan,
)
from aec_bench.experiments.retrieval_state_continuity.scenario import (
    PreparedTrialScenario,
    prepare_trial_scenario,
    score_trial_scenario,
)
from aec_bench.meta_harness.immutable_artifact_store import (
    EvidenceRepository,
    ImmutableArtifact,
    ImmutableArtifactIntegrityError,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_serialization import (
    pump_station_artifact_bytes,
)
from aec_bench.trajectory.writer import TrajectoryWriter

MODEL_TRIAL_EXECUTION_SCHEMA_VERSION: Literal["aecbench.retrieval-state-model-trial.v1"] = (
    "aecbench.retrieval-state-model-trial.v1"
)
MODEL_STUDY_EXECUTION_SCHEMA_VERSION: Literal["aecbench.retrieval-state-model-study.v1"] = (
    "aecbench.retrieval-state-model-study.v1"
)

_MANIFEST_ADAPTER = TypeAdapter(StudyManifest)
_PLAN_ADAPTER = TypeAdapter(StudyPlan)
_DELIVERY_ADAPTER = TypeAdapter(TreatmentDelivery)
_OBSERVATION_ADAPTER = TypeAdapter(StudyObservation)
_REPORT_ADAPTER = TypeAdapter(StudyReport)


class ModelTrialExecution(ContentAddressedModel):
    """Immutable operational evidence for one public-model trial."""

    schema_version: Literal["aecbench.retrieval-state-model-trial.v1"] = MODEL_TRIAL_EXECUTION_SCHEMA_VERSION
    manifest_content_sha256: str
    plan_content_sha256: str
    block_id: NonEmptyStr
    trial_id: NonEmptyStr
    treatment: Treatment
    phase: StudyPhase
    provider_id: NonEmptyStr
    credential_profile_id: NonEmptyStr
    model_id: NonEmptyStr
    resolved_model: NonEmptyStr
    adapter_id: NonEmptyStr
    adapter_status: NonEmptyStr
    adapter_failure_kind: NonEmptyStr | None
    start_state_sha256: str
    final_state_sha256: str
    event_schedule_sha256: str
    structured_handover_sha256: str
    delivered_carrier_sha256: str
    shared_visible_input_sha256: str
    output_sha256: str
    conversation_sha256: str
    trajectory_sha256: str
    provider_call_count: NonNegativeInt
    agent_turn_count: NonNegativeInt
    input_token_count: NonNegativeInt
    output_token_count: NonNegativeInt
    reported_analysis_token_count: NonNegativeInt | None
    analysis_token_reporting: Literal["not_reported_separately_by_adapter"] = "not_reported_separately_by_adapter"
    analysis_tokens_included_in: Literal["output_tokens"] = "output_tokens"
    total_token_count: NonNegativeInt
    maximum_input_tokens_in_one_call: NonNegativeInt
    maximum_output_tokens_in_one_call: NonNegativeInt
    spend_currency: Literal["USD"] = "USD"
    spend_microunits: NonNegativeInt
    search_call_count: NonNegativeInt
    fetch_call_count: NonNegativeInt
    material_evidence_acquired: bool
    material_evidence_used: bool
    conservative_action: bool
    epistemic_decision_failure: bool | None
    world_verification_valid: bool
    temporal_verification_valid: bool
    task_reward_mutation_count: Literal[0] = 0
    secret_scan_passed: Literal[True] = True

    @field_validator(
        "manifest_content_sha256",
        "plan_content_sha256",
        "start_state_sha256",
        "final_state_sha256",
        "event_schedule_sha256",
        "structured_handover_sha256",
        "delivered_carrier_sha256",
        "shared_visible_input_sha256",
        "output_sha256",
        "conversation_sha256",
        "trajectory_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_usage(self) -> ModelTrialExecution:
        if self.total_token_count != self.input_token_count + self.output_token_count:
            raise ValueError("trial total tokens differ from input plus output")
        if self.reported_analysis_token_count is not None:
            raise ValueError("selected adapter does not report analysis tokens separately")
        return self


class ModelStudyExecution(ContentAddressedModel):
    """Complete model-run identity and aggregate usage for one study generation."""

    schema_version: Literal["aecbench.retrieval-state-model-study.v1"] = MODEL_STUDY_EXECUTION_SCHEMA_VERSION
    manifest_content_sha256: str
    plan_content_sha256: str
    report_content_sha256: str
    phase: StudyPhase
    planned_trial_count: NonNegativeInt
    executed_trial_count: NonNegativeInt
    provider_call_count: NonNegativeInt
    input_token_count: NonNegativeInt
    output_token_count: NonNegativeInt
    reported_analysis_token_count: None = None
    analysis_token_reporting: Literal["not_reported_separately_by_adapter"] = "not_reported_separately_by_adapter"
    analysis_tokens_included_in: Literal["output_tokens"] = "output_tokens"
    total_token_count: NonNegativeInt
    spend_currency: Literal["USD"] = "USD"
    spend_microunits: NonNegativeInt
    execution_content_sha256: tuple[str, ...]

    @field_validator(
        "manifest_content_sha256",
        "plan_content_sha256",
        "report_content_sha256",
        "execution_content_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str | tuple[str, ...]) -> str | tuple[str, ...]:
        if isinstance(value, tuple):
            return tuple(validate_sha256(item) for item in value)
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_totals(self) -> ModelStudyExecution:
        if self.executed_trial_count != len(self.execution_content_sha256):
            raise ValueError("study execution count differs from trial identities")
        if self.total_token_count != self.input_token_count + self.output_token_count:
            raise ValueError("study total tokens differ from input plus output")
        return self


@dataclass(frozen=True, slots=True)
class PublishedModelStudy:
    """Published real-model study plus independently reloadable references."""

    manifest: StudyManifest
    plan: StudyPlan
    deliveries: tuple[TreatmentDelivery, ...]
    observations: tuple[StudyObservation, ...]
    executions: tuple[ModelTrialExecution, ...]
    report: StudyReport
    execution: ModelStudyExecution
    manifest_reference: ImmutableArtifact
    plan_reference: ImmutableArtifact
    report_reference: ImmutableArtifact
    execution_reference: ImmutableArtifact


@dataclass(frozen=True, slots=True)
class VerifiedModelStudyProgress:
    """Completed trial evidence that is safe to reuse after interruption."""

    deliveries: tuple[TreatmentDelivery, ...]
    observations: tuple[StudyObservation, ...]
    executions: tuple[ModelTrialExecution, ...]
    completed_trial_ids: frozenset[str]


def run_model_study(
    root: Path,
    *,
    phase: StudyPhase,
    registry: Any | None = None,
) -> PublishedModelStudy:
    """Run the authorized shakedown pair or the complete confirmatory schedule."""

    if phase not in {StudyPhase.SHAKEDOWN, StudyPhase.CONFIRMATORY}:
        raise ValueError("model study must be shakedown or confirmatory")
    manifest = build_model_manifest(phase)
    plan = build_study_plan(manifest)
    destination = Path(root).resolve()
    if not destination.exists():
        destination.mkdir(parents=True, mode=0o700)
    repository = EvidenceRepository(destination, host_private=True)
    manifest_reference = _publish_or_verify_single_model(
        repository=repository,
        collection="manifests",
        filename="study-manifest.json",
        model=manifest,
        adapter=_MANIFEST_ADAPTER,
    )
    plan_reference = _publish_or_verify_single_model(
        repository=repository,
        collection="plans",
        filename="study-plan.json",
        model=plan,
        adapter=_PLAN_ADAPTER,
    )
    selected_trials = plan.blocks[0].trials if phase is StudyPhase.SHAKEDOWN else plan.trials
    block_by_id = {item.block_id: item for item in plan.blocks}
    progress = _load_completed_trial_evidence(
        repository=repository,
        manifest=manifest,
        plan=plan,
        selected_trials=selected_trials,
    )
    deliveries = {item.trial_id: item for item in progress.deliveries}
    observations = {item.trial_id: item for item in progress.observations}
    executions = {item.trial_id: item for item in progress.executions}
    selected_registry: Any | None = None
    for trial in selected_trials:
        if trial.trial_id in progress.completed_trial_ids:
            continue
        block = block_by_id[trial.block_id]
        trial_root = destination / "runs" / f"{trial.execution_position:03d}-{trial.trial_id}"
        if trial_root.exists():
            raise ImmutableArtifactIntegrityError(f"interrupted trial requires explicit recovery: {trial.trial_id}")
        prepared = prepare_trial_scenario(
            trial_root / "world",
            manifest=manifest,
            plan=plan,
            block=block,
            trial=trial,
        )
        agent_root = trial_root / "agent"
        agent_root.mkdir(parents=True, mode=0o700)
        trajectory = TrajectoryWriter(path=str(agent_root / "trajectory.jsonl"))
        try:
            execution_spec = manifest.model_execution
            if execution_spec is None:
                raise ValueError("model study has no execution specification")
            if selected_registry is None:
                selected_registry = registry or _local_adapter_registry()
            adapter = selected_registry.build(
                adapter_kind=execution_spec.adapter_id,
                model_name=execution_spec.model_id,
                workspace=str(agent_root),
                trajectory_writer=trajectory,
                native_tools=list(prepared.tools.native_tools),
                enable_bash=False,
                cache=False,
            )
            adapter_result = adapter.execute(
                AdapterRequest(
                    instruction=_model_instruction(prepared),
                    system_prompt=_model_system_prompt(),
                    tools=list(prepared.tools.tool_specs),
                    configuration=_adapter_configuration(manifest),
                    output_path=str(agent_root / "output.md"),
                    output_format="markdown",
                )
            )
        finally:
            trajectory.close()
        _write_adapter_evidence(agent_root, adapter_result)
        delivery = _delivery(manifest, plan, prepared)
        observation, execution = _trial_result(
            manifest=manifest,
            plan=plan,
            prepared=prepared,
            delivery=delivery,
            adapter_result=adapter_result,
            agent_root=agent_root,
        )
        repository.publish_content_addressed_model(
            collection="treatment-deliveries",
            filename="treatment-delivery.json",
            model=delivery,
            adapter=_DELIVERY_ADAPTER,
        )
        repository.publish_content_addressed_model(
            collection="observations",
            filename="observation.json",
            model=observation,
            adapter=_OBSERVATION_ADAPTER,
        )
        repository.publish_content_addressed_model(
            collection="trial-executions",
            filename="trial-execution.json",
            model=execution,
            adapter=TypeAdapter(ModelTrialExecution),
        )
        deliveries[trial.trial_id] = delivery
        observations[trial.trial_id] = observation
        executions[trial.trial_id] = execution

    delivery_tuple = tuple(deliveries[trial.trial_id] for trial in selected_trials)
    observation_tuple = tuple(observations[trial.trial_id] for trial in selected_trials)
    execution_tuple = tuple(executions[trial.trial_id] for trial in selected_trials)
    report = analyse_study(
        manifest=manifest,
        plan=plan,
        deliveries=delivery_tuple,
        observations=observation_tuple,
    )
    report_reference = _publish_or_verify_single_model(
        repository=repository,
        collection="reports",
        filename="study-report.json",
        model=report,
        adapter=_REPORT_ADAPTER,
    )
    study_execution = ModelStudyExecution(
        manifest_content_sha256=manifest.content_sha256,
        plan_content_sha256=plan.content_sha256,
        report_content_sha256=report.content_sha256,
        phase=phase,
        planned_trial_count=len(plan.trials),
        executed_trial_count=len(execution_tuple),
        provider_call_count=sum(item.provider_call_count for item in execution_tuple),
        input_token_count=sum(item.input_token_count for item in execution_tuple),
        output_token_count=sum(item.output_token_count for item in execution_tuple),
        total_token_count=sum(item.total_token_count for item in execution_tuple),
        spend_microunits=sum(item.spend_microunits for item in execution_tuple),
        execution_content_sha256=tuple(item.content_sha256 for item in execution_tuple),
    )
    execution_adapter = TypeAdapter(ModelStudyExecution)
    execution_reference = _publish_or_verify_single_model(
        repository=repository,
        collection="study-executions",
        filename="study-execution.json",
        model=study_execution,
        adapter=execution_adapter,
    )
    _assert_no_secret_material(destination)
    reloaded = reload_and_verify_model_study(
        root=destination,
        execution_content_sha256=study_execution.content_sha256,
    )
    if reloaded != study_execution:
        raise ImmutableArtifactIntegrityError("reloaded model study differs")
    return PublishedModelStudy(
        manifest=manifest,
        plan=plan,
        deliveries=delivery_tuple,
        observations=observation_tuple,
        executions=execution_tuple,
        report=report,
        execution=study_execution,
        manifest_reference=manifest_reference,
        plan_reference=plan_reference,
        report_reference=report_reference,
        execution_reference=execution_reference,
    )


def _load_completed_trial_evidence(
    *,
    repository: EvidenceRepository,
    manifest: StudyManifest,
    plan: StudyPlan,
    selected_trials: tuple[PlannedTrial, ...],
) -> VerifiedModelStudyProgress:
    """Reload and join only complete, content-addressed trial evidence."""

    deliveries = _load_content_collection(
        repository=repository,
        collection="treatment-deliveries",
        filename="treatment-delivery.json",
        adapter=_DELIVERY_ADAPTER,
    )
    observations = _load_content_collection(
        repository=repository,
        collection="observations",
        filename="observation.json",
        adapter=_OBSERVATION_ADAPTER,
    )
    executions = _load_content_collection(
        repository=repository,
        collection="trial-executions",
        filename="trial-execution.json",
        adapter=TypeAdapter(ModelTrialExecution),
    )
    delivery_by_id = _unique_trial_records(deliveries, label="treatment delivery")
    observation_by_id = _unique_trial_records(observations, label="observation")
    execution_by_id = _unique_trial_records(executions, label="trial execution")
    published_ids = set(delivery_by_id) | set(observation_by_id) | set(execution_by_id)
    if not (set(delivery_by_id) == set(observation_by_id) == set(execution_by_id)):
        raise ImmutableArtifactIntegrityError("incomplete published trial evidence")
    selected_by_id = {trial.trial_id: trial for trial in selected_trials}
    unknown_ids = published_ids - set(selected_by_id)
    if unknown_ids:
        raise ImmutableArtifactIntegrityError(
            f"published trial evidence is outside the selected schedule: {sorted(unknown_ids)}"
        )
    block_by_id = {block.block_id: block for block in plan.blocks}
    expected_source = (
        ObservationSource.GENERATED_ANALYSIS_FIXTURE
        if manifest.phase is StudyPhase.ANALYSIS_FIXTURE
        else ObservationSource.SHAKEDOWN
        if manifest.phase is StudyPhase.SHAKEDOWN
        else ObservationSource.CONFIRMATORY
    )
    for trial_id in published_ids:
        trial = selected_by_id[trial_id]
        block = block_by_id[trial.block_id]
        delivery = delivery_by_id[trial_id]
        observation = observation_by_id[trial_id]
        execution = execution_by_id[trial_id]
        common_identity = (
            delivery.manifest_content_sha256 == manifest.content_sha256
            and delivery.plan_content_sha256 == plan.content_sha256
            and observation.manifest_content_sha256 == manifest.content_sha256
            and observation.plan_content_sha256 == plan.content_sha256
            and execution.manifest_content_sha256 == manifest.content_sha256
            and execution.plan_content_sha256 == plan.content_sha256
            and delivery.block_id == observation.block_id == execution.block_id == block.block_id
            and delivery.treatment == observation.treatment == execution.treatment == trial.treatment
            and delivery.source is observation.source is expected_source
            and delivery.non_treatment_input_sha256 == block.non_treatment_input_sha256
            and delivery.current_actor_view_sha256 == block.current_actor_view_sha256
            and delivery.history_snapshot_sha256 == observation.history_snapshot_sha256 == block.history_snapshot_sha256
            and delivery.event_schedule_sha256 == observation.event_schedule_sha256 == block.event_schedule_sha256
            and delivery.base_carrier_sha256 == block.base_carrier_sha256
            and observation.delivery_content_sha256 == delivery.content_sha256
            and observation.world_history_seed == block.world_history_seed
            and observation.sampling_replicate == block.sampling_replicate
            and observation.budget_sha256 == trial.budget_sha256
            and execution.phase is manifest.phase
            and execution.delivered_carrier_sha256 == delivery.delivered_carrier_sha256
            and execution.provider_call_count == observation.provider_call_count
            and execution.agent_turn_count == observation.agent_turn_count
            and execution.input_token_count == observation.input_token_count
            and execution.output_token_count == observation.output_token_count
            and execution.total_token_count == observation.total_token_count
            and execution.spend_microunits == observation.spend_microunits
            and execution.search_call_count == observation.search_call_count
            and execution.fetch_call_count == observation.fetch_call_count
            and execution.material_evidence_acquired == observation.material_evidence_acquired
            and execution.material_evidence_used == observation.material_evidence_used
            and execution.conservative_action == observation.conservative_action
            and execution.epistemic_decision_failure == observation.epistemic_decision_failure
            and execution.task_reward_mutation_count == observation.task_reward_mutation_count
        )
        if not common_identity:
            raise ImmutableArtifactIntegrityError(f"published trial evidence identity mismatch: {trial_id}")
    ordered = tuple(trial for trial in selected_trials if trial.trial_id in published_ids)
    return VerifiedModelStudyProgress(
        deliveries=tuple(delivery_by_id[trial.trial_id] for trial in ordered),
        observations=tuple(observation_by_id[trial.trial_id] for trial in ordered),
        executions=tuple(execution_by_id[trial.trial_id] for trial in ordered),
        completed_trial_ids=frozenset(published_ids),
    )


def _load_content_collection(
    *,
    repository: EvidenceRepository,
    collection: str,
    filename: str,
    adapter: TypeAdapter[Any],
) -> tuple[Any, ...]:
    models: list[Any] = []
    for relative_path in repository.list_child_files(collection, filename=filename):
        model = repository.load_canonical_model(relative_path, adapter)
        expected_path = repository.content_model_path(
            collection=collection,
            content_sha256=model.content_sha256,
            filename=filename,
        )
        if relative_path != expected_path:
            raise ImmutableArtifactIntegrityError(f"content-addressed evidence uses the wrong path: {relative_path}")
        models.append(model)
    return tuple(models)


def _unique_trial_records(records: tuple[Any, ...], *, label: str) -> dict[str, Any]:
    indexed: dict[str, Any] = {}
    for record in records:
        if record.trial_id in indexed:
            raise ImmutableArtifactIntegrityError(f"duplicate {label} for trial: {record.trial_id}")
        indexed[record.trial_id] = record
    return indexed


def _publish_or_verify_single_model(
    *,
    repository: EvidenceRepository,
    collection: str,
    filename: str,
    model: Any,
    adapter: TypeAdapter[Any],
) -> ImmutableArtifact:
    existing = _load_content_collection(
        repository=repository,
        collection=collection,
        filename=filename,
        adapter=adapter,
    )
    if existing and (len(existing) != 1 or existing[0] != model):
        raise ImmutableArtifactIntegrityError(f"existing {collection} do not match the requested study generation")
    return repository.publish_content_addressed_model(
        collection=collection,
        filename=filename,
        model=model,
        adapter=adapter,
    ).artifact


def reload_and_verify_model_study(
    *,
    root: Path,
    execution_content_sha256: str,
) -> ModelStudyExecution:
    """Reload exact model evidence and recompute all aggregate identities."""

    repository = EvidenceRepository(Path(root).resolve(), host_private=True)
    execution_adapter = TypeAdapter(ModelStudyExecution)
    selected = repository.load_content_addressed_model(
        collection="study-executions",
        content_sha256=execution_content_sha256,
        filename="study-execution.json",
        adapter=execution_adapter,
    ).model
    report = reload_and_verify_study_report(
        root=Path(root),
        report_content_sha256=selected.report_content_sha256,
    )
    manifest = repository.load_content_addressed_model(
        collection="manifests",
        content_sha256=selected.manifest_content_sha256,
        filename="study-manifest.json",
        adapter=_MANIFEST_ADAPTER,
    ).model
    plan = repository.load_content_addressed_model(
        collection="plans",
        content_sha256=selected.plan_content_sha256,
        filename="study-plan.json",
        adapter=_PLAN_ADAPTER,
    ).model
    trials = tuple(
        repository.load_content_addressed_model(
            collection="trial-executions",
            content_sha256=content_sha256,
            filename="trial-execution.json",
            adapter=TypeAdapter(ModelTrialExecution),
        ).model
        for content_sha256 in selected.execution_content_sha256
    )
    recomputed = ModelStudyExecution(
        manifest_content_sha256=manifest.content_sha256,
        plan_content_sha256=plan.content_sha256,
        report_content_sha256=report.content_sha256,
        phase=manifest.phase,
        planned_trial_count=len(plan.trials),
        executed_trial_count=len(trials),
        provider_call_count=sum(item.provider_call_count for item in trials),
        input_token_count=sum(item.input_token_count for item in trials),
        output_token_count=sum(item.output_token_count for item in trials),
        total_token_count=sum(item.total_token_count for item in trials),
        spend_microunits=sum(item.spend_microunits for item in trials),
        execution_content_sha256=tuple(item.content_sha256 for item in trials),
    )
    if recomputed != selected:
        raise ImmutableArtifactIntegrityError("stored model-study totals differ from reload")
    return selected


def _delivery(
    manifest: StudyManifest,
    plan: StudyPlan,
    prepared: PreparedTrialScenario,
) -> TreatmentDelivery:
    source = ObservationSource.SHAKEDOWN if manifest.phase is StudyPhase.SHAKEDOWN else ObservationSource.CONFIRMATORY
    return TreatmentDelivery(
        manifest_content_sha256=manifest.content_sha256,
        plan_content_sha256=plan.content_sha256,
        block_id=prepared.block.block_id,
        trial_id=prepared.trial.trial_id,
        treatment=prepared.trial.treatment,
        source=source,
        status=TreatmentDeliveryStatus.DELIVERED,
        delivered_before_outcome=True,
        non_treatment_input_sha256=prepared.block.non_treatment_input_sha256,
        current_actor_view_sha256=prepared.block.current_actor_view_sha256,
        history_snapshot_sha256=prepared.block.history_snapshot_sha256,
        event_schedule_sha256=prepared.block.event_schedule_sha256,
        base_carrier_sha256=prepared.block.base_carrier_sha256,
        treatment_projection_sha256=prepared.treatment_projection_sha256,
        delivered_carrier_sha256=prepared.carrier.content_sha256,
        visible_input_audit_sha256=canonical_content_sha256(
            {
                "shared_visible_input_sha256": prepared.shared_visible_input_sha256,
                "declared_treatment_projection_sha256": prepared.treatment_projection_sha256,
                "only_declared_difference": True,
            }
        ),
        provider_call_count=0,
    )


def _trial_result(
    *,
    manifest: StudyManifest,
    plan: StudyPlan,
    prepared: PreparedTrialScenario,
    delivery: TreatmentDelivery,
    adapter_result: AdapterResult,
    agent_root: Path,
) -> tuple[StudyObservation, ModelTrialExecution]:
    score = score_trial_scenario(prepared)
    world_verification = prepared.session.verify()
    temporal_verification = prepared.session.verify_temporal_evidence()
    failure_kind, ineligibility = _classify_failure(
        adapter_result,
        world_valid=world_verification.valid,
        temporal_valid=temporal_verification.valid,
    )
    endpoint = (
        None
        if ineligibility is not None
        else True
        if failure_kind is not FailureKind.NONE
        else score.epistemic_decision_failure
    )
    input_tokens = adapter_result.usage_input_tokens or 0
    output_tokens = adapter_result.usage_output_tokens or 0
    provider_calls = adapter_result.usage_model_calls or 0
    spend = _spend_microunits(input_tokens=input_tokens, output_tokens=output_tokens)
    source = ObservationSource.SHAKEDOWN if manifest.phase is StudyPhase.SHAKEDOWN else ObservationSource.CONFIRMATORY
    observation = StudyObservation(
        manifest_content_sha256=manifest.content_sha256,
        plan_content_sha256=plan.content_sha256,
        block_id=prepared.block.block_id,
        trial_id=prepared.trial.trial_id,
        world_history_seed=prepared.block.world_history_seed,
        sampling_replicate=prepared.block.sampling_replicate,
        treatment=prepared.trial.treatment,
        source=source,
        delivery_content_sha256=delivery.content_sha256,
        history_snapshot_sha256=prepared.block.history_snapshot_sha256,
        event_schedule_sha256=prepared.block.event_schedule_sha256,
        budget_sha256=prepared.trial.budget_sha256,
        failure_kind=failure_kind,
        epistemic_decision_failure=endpoint,
        ineligibility_reason=ineligibility,
        material_evidence_acquired=score.material_evidence_acquired,
        material_evidence_used=score.material_evidence_used,
        stale_source_relied_on=score.stale_source_relied_on,
        conservative_action=score.conservative_action,
        search_call_count=score.search_call_count,
        fetch_call_count=score.fetch_call_count,
        visible_retrieval_bytes=score.visible_retrieval_bytes,
        visible_retrieval_tokens=score.visible_retrieval_tokens,
        agent_turn_count=adapter_result.turns_used or 0,
        provider_call_count=provider_calls,
        input_token_count=input_tokens,
        output_token_count=output_tokens,
        reported_analysis_token_count=None,
        analysis_tokens_included_in_output=True,
        total_token_count=input_tokens + output_tokens,
        spend_currency="USD",
        spend_microunits=spend,
        study_outcome_eligible=manifest.phase is StudyPhase.CONFIRMATORY,
        task_reward_mutation_count=0,
    )
    execution_spec = manifest.model_execution
    if execution_spec is None:
        raise ValueError("model study has no execution specification")
    execution = ModelTrialExecution(
        manifest_content_sha256=manifest.content_sha256,
        plan_content_sha256=plan.content_sha256,
        block_id=prepared.block.block_id,
        trial_id=prepared.trial.trial_id,
        treatment=prepared.trial.treatment,
        phase=manifest.phase,
        provider_id=execution_spec.provider_id,
        credential_profile_id=execution_spec.credential_profile_id,
        model_id=execution_spec.model_id,
        resolved_model=adapter_result.resolved_model,
        adapter_id=execution_spec.adapter_id,
        adapter_status=adapter_result.agent_output.status.value,
        adapter_failure_kind=(None if adapter_result.failure_kind is None else adapter_result.failure_kind.value),
        start_state_sha256=prepared.session.run.manifest.initial_state_id,
        final_state_sha256=prepared.session.result.snapshot.state_id,
        event_schedule_sha256=prepared.session.event_schedule_sha256,
        structured_handover_sha256=prepared.handover.handover_id,
        delivered_carrier_sha256=prepared.carrier.content_sha256,
        shared_visible_input_sha256=prepared.shared_visible_input_sha256,
        output_sha256=_file_sha256(agent_root / "output.md"),
        conversation_sha256=_file_sha256(agent_root / "conversation.jsonl"),
        trajectory_sha256=_file_sha256(agent_root / "trajectory.jsonl"),
        provider_call_count=provider_calls,
        agent_turn_count=adapter_result.turns_used or 0,
        input_token_count=input_tokens,
        output_token_count=output_tokens,
        reported_analysis_token_count=None,
        total_token_count=input_tokens + output_tokens,
        maximum_input_tokens_in_one_call=(adapter_result.maximum_input_tokens_in_one_call or 0),
        maximum_output_tokens_in_one_call=(adapter_result.maximum_output_tokens_in_one_call or 0),
        spend_microunits=spend,
        search_call_count=score.search_call_count,
        fetch_call_count=score.fetch_call_count,
        material_evidence_acquired=score.material_evidence_acquired,
        material_evidence_used=score.material_evidence_used,
        conservative_action=score.conservative_action,
        epistemic_decision_failure=endpoint,
        world_verification_valid=world_verification.valid,
        temporal_verification_valid=temporal_verification.valid,
    )
    return observation, execution


def _classify_failure(
    result: AdapterResult,
    *,
    world_valid: bool,
    temporal_valid: bool,
) -> tuple[FailureKind, PairIneligibilityReason | None]:
    if not world_valid or not temporal_valid:
        return FailureKind.HOST_FAILURE_AFTER_DELIVERY, PairIneligibilityReason.HOST_FAILURE
    if result.failure_kind is None:
        return FailureKind.NONE, None
    if result.failure_kind is AdapterFailureKind.TIMEOUT:
        return FailureKind.MODEL_TIMEOUT, None
    if result.failure_kind is AdapterFailureKind.MISSING_OUTPUT:
        return FailureKind.MODEL_EMPTY_OUTPUT, None
    return FailureKind.OUTPUT_CONTRACT_FAILURE, None


def _model_system_prompt() -> str:
    return (
        "You are the accountable wastewater pump-station steward for a fresh "
        "tenure. Use only the declared station and documentary-evidence tools. "
        "Use live identifiers. Do not invent evidence or references. A current "
        "reading does not cancel a restriction or a required follow-up. Keep "
        "each request_id and proposal_id unique."
    )


def _model_instruction(prepared: PreparedTrialScenario) -> str:
    return (
        "Manage the live station at the open decision point. Documentary access "
        "can change with world time. Review current documentary access and any "
        "unresolved retrieval work. Before you finish, resolve the Pump A "
        "obstruction uncertainty with one safe consequential station proposal. "
        "Use supporting evidence through the declared reliance field. Do not "
        "guess a reference. "
        "Return a short factual summary after the proposal.\n\n"
        "STRUCTURED HANDOVER\n"
        + pump_station_artifact_bytes(prepared.handover).decode("utf-8")
        + "\n\nRETRIEVAL CONTEXT\n"
        + prepared.carrier.model_dump_json(indent=2)
    )


def _adapter_configuration(manifest: StudyManifest) -> dict[str, Any]:
    specification = manifest.model_execution
    if specification is None:
        raise ValueError("model study has no execution specification")
    return {
        "max_turns": specification.maximum_agent_turns,
        "max_tool_calls": specification.maximum_tool_calls,
        "max_output_tokens_per_call": specification.maximum_output_tokens_per_call,
        "count_tokens_before_request": specification.count_tokens_before_request,
        "cache_enabled": specification.cache_enabled,
        "advisor_enabled": specification.advisor_enabled,
        "bash_enabled": specification.bash_enabled,
    }


def _spend_microunits(*, input_tokens: int, output_tokens: int) -> int:
    dollars = (Decimal(input_tokens) * Decimal("3.30") + Decimal(output_tokens) * Decimal("16.50")) / Decimal(1_000_000)
    return int((dollars * Decimal(1_000_000)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _write_adapter_evidence(destination: Path, result: AdapterResult) -> None:
    output = result.raw_output_text or ""
    (destination / "output.md").write_text(output, encoding="utf-8")
    _write_json(
        destination / "agent-result.json",
        {
            "status": result.agent_output.status.value,
            "adapter_name": result.adapter_name,
            "resolved_model": result.resolved_model,
            "configuration_record": result.configuration_record,
            "turns_used": result.turns_used,
            "provider_calls": result.usage_model_calls,
            "input_tokens": result.usage_input_tokens,
            "output_tokens": result.usage_output_tokens,
            "reported_analysis_tokens": None,
            "analysis_token_reporting": "not_reported_separately_by_adapter",
            "analysis_tokens_included_in": "output_tokens",
            "maximum_input_tokens_in_one_call": result.maximum_input_tokens_in_one_call,
            "maximum_output_tokens_in_one_call": result.maximum_output_tokens_in_one_call,
            "cache_read_tokens": result.usage_cache_read_tokens,
            "cache_write_tokens": result.usage_cache_write_tokens,
            "advisor_calls": result.usage_advisor_calls,
            "failure_kind": None if result.failure_kind is None else result.failure_kind.value,
        },
    )
    with (destination / "conversation.jsonl").open("w", encoding="utf-8") as handle:
        for entry in result.transcript:
            handle.write(
                json.dumps(
                    {
                        "role": entry.role.value,
                        "event": entry.event.value,
                        "content": entry.content,
                        "tool_name": entry.tool_name,
                        "tool_call_id": entry.tool_call_id,
                    },
                    sort_keys=True,
                )
                + "\n"
            )


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _assert_no_secret_material(root: Path) -> None:
    forbidden = (
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        '"accessKeyId"',
        '"secretAccessKey"',
        '"sessionToken"',
    )
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if any(marker in text for marker in forbidden):
            raise ValueError(f"credential-shaped material found in {path}")


def _local_adapter_registry() -> Any:
    from aec_bench.adapters.local_registry import LocalAdapterRegistry

    return LocalAdapterRegistry()
