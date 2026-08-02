# ABOUTME: Generates provider-free evidence for the retrieval-state analysis path.
# ABOUTME: Marks every generated record as ineligible for a model study conclusion.

from __future__ import annotations

from aec_bench.contracts.harness_kernel import canonical_content_sha256
from aec_bench.experiments.retrieval_state_continuity.contracts import (
    FailureKind,
    FixtureEvidence,
    ObservationSource,
    StudyManifest,
    StudyObservation,
    StudyPhase,
    StudyPlan,
    Treatment,
    TreatmentDelivery,
    TreatmentDeliveryStatus,
)


def build_fixture_evidence(*, manifest: StudyManifest, plan: StudyPlan) -> FixtureEvidence:
    """Create complete generated inputs without a model or study outcome."""

    selected_manifest = StudyManifest.model_validate(manifest.model_dump(mode="json"))
    selected_plan = StudyPlan.model_validate(plan.model_dump(mode="json"))
    if selected_manifest.phase is not StudyPhase.ANALYSIS_FIXTURE:
        raise ValueError("provider-free evidence requires analysis_fixture authority")
    if selected_plan.manifest_content_sha256 != selected_manifest.content_sha256:
        raise ValueError("fixture plan does not belong to its manifest")

    deliveries: list[TreatmentDelivery] = []
    observations: list[StudyObservation] = []
    for block in selected_plan.blocks:
        treatment_projection_sha256 = canonical_content_sha256(
            {
                "projection_id": selected_manifest.treatment.projection_id,
                "history_snapshot_sha256": block.history_snapshot_sha256,
                "unresolved_search": "pre-handover-no-accessible-result",
                "remaining_budget": selected_manifest.budget.model_dump(mode="json"),
            }
        )
        for trial in block.trials:
            projection = treatment_projection_sha256 if trial.treatment is Treatment.RETRIEVAL_STATE_PRESERVED else None
            delivered_carrier_sha256 = canonical_content_sha256(
                {
                    "base_carrier_sha256": block.base_carrier_sha256,
                    "treatment_projection_sha256": projection,
                }
            )
            delivery = TreatmentDelivery(
                manifest_content_sha256=selected_manifest.content_sha256,
                plan_content_sha256=selected_plan.content_sha256,
                block_id=block.block_id,
                trial_id=trial.trial_id,
                treatment=trial.treatment,
                source=ObservationSource.GENERATED_ANALYSIS_FIXTURE,
                status=TreatmentDeliveryStatus.DELIVERED,
                delivered_before_outcome=True,
                non_treatment_input_sha256=block.non_treatment_input_sha256,
                current_actor_view_sha256=block.current_actor_view_sha256,
                history_snapshot_sha256=block.history_snapshot_sha256,
                event_schedule_sha256=block.event_schedule_sha256,
                base_carrier_sha256=block.base_carrier_sha256,
                treatment_projection_sha256=projection,
                delivered_carrier_sha256=delivered_carrier_sha256,
                visible_input_audit_sha256=canonical_content_sha256(
                    {
                        "non_treatment_input_sha256": block.non_treatment_input_sha256,
                        "declared_treatment_projection_sha256": projection,
                        "only_declared_difference": True,
                    }
                ),
                provider_call_count=0,
            )
            deliveries.append(delivery)
            decision_failure = _fixture_failure(
                sampling_replicate=block.sampling_replicate,
                treatment=trial.treatment,
            )
            observations.append(
                StudyObservation(
                    manifest_content_sha256=selected_manifest.content_sha256,
                    plan_content_sha256=selected_plan.content_sha256,
                    block_id=block.block_id,
                    trial_id=trial.trial_id,
                    world_history_seed=block.world_history_seed,
                    sampling_replicate=block.sampling_replicate,
                    treatment=trial.treatment,
                    source=ObservationSource.GENERATED_ANALYSIS_FIXTURE,
                    delivery_content_sha256=delivery.content_sha256,
                    history_snapshot_sha256=block.history_snapshot_sha256,
                    event_schedule_sha256=block.event_schedule_sha256,
                    budget_sha256=trial.budget_sha256,
                    failure_kind=FailureKind.NONE,
                    epistemic_decision_failure=decision_failure,
                    ineligibility_reason=None,
                    material_evidence_acquired=not decision_failure,
                    material_evidence_used=not decision_failure,
                    stale_source_relied_on=False,
                    conservative_action=False,
                    search_call_count=1,
                    fetch_call_count=0 if decision_failure else 1,
                    visible_retrieval_bytes=0 if decision_failure else 512,
                    visible_retrieval_tokens=0 if decision_failure else 96,
                    agent_turn_count=4,
                    provider_call_count=0,
                    input_token_count=0,
                    output_token_count=0,
                    reported_analysis_token_count=None,
                    analysis_tokens_included_in_output=False,
                    total_token_count=0,
                    spend_currency=None,
                    spend_microunits=0,
                    study_outcome_eligible=False,
                    task_reward_mutation_count=0,
                )
            )
    return FixtureEvidence(deliveries=tuple(deliveries), observations=tuple(observations))


def _fixture_failure(*, sampling_replicate: int, treatment: Treatment) -> bool:
    if treatment is Treatment.RETRIEVAL_STATE_ABSENT:
        return True
    return sampling_replicate <= 2
