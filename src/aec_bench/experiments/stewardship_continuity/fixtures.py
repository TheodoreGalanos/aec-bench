# ABOUTME: Generates deterministic provider-free evidence for the ASW-4A analysis path.
# ABOUTME: Marks every generated value as ineligible for study-outcome claims.

from __future__ import annotations

from aec_bench.contracts.harness_kernel import canonical_content_sha256
from aec_bench.experiments.stewardship_continuity.contracts import (
    ContinuityFailureKind,
    ContinuityHistoryClass,
    ContinuityObservation,
    ContinuityStudyManifest,
    ContinuityStudyPhase,
    ContinuityStudyPlan,
    ContinuityTreatment,
    ObservationSource,
    ProviderFreeFixtureEvidence,
    TreatmentDeliveryRecord,
    TreatmentDeliveryStatus,
)


def build_provider_free_fixture_evidence(
    *,
    manifest: ContinuityStudyManifest,
    plan: ContinuityStudyPlan,
) -> ProviderFreeFixtureEvidence:
    """Create complete synthetic analysis inputs without executing a model."""

    selected_manifest = ContinuityStudyManifest.model_validate(
        manifest.model_dump(mode="json"),
    )
    selected_plan = ContinuityStudyPlan.model_validate(
        plan.model_dump(mode="json"),
    )
    if selected_manifest.phase is not ContinuityStudyPhase.ANALYSIS_FIXTURE:
        raise ValueError("provider-free fixture evidence requires an analysis-fixture manifest")
    if selected_plan.manifest_content_sha256 != selected_manifest.content_sha256:
        raise ValueError("continuity fixture plan does not belong to its manifest")

    deliveries: list[TreatmentDeliveryRecord] = []
    observations: list[ContinuityObservation] = []

    for block in selected_plan.blocks:
        current_state_equivalence_sha256 = canonical_content_sha256(
            {
                "kind": "generated-current-state-equivalence",
                "history_slot_id": block.history_slot_id,
            }
        )
        current_duties_sha256 = canonical_content_sha256(
            {
                "kind": "generated-current-duties",
                "history_slot_id": block.history_slot_id,
            }
        )
        for trial in block.trials:
            delivery = TreatmentDeliveryRecord(
                manifest_content_sha256=selected_manifest.content_sha256,
                plan_content_sha256=selected_plan.content_sha256,
                block_id=block.block_id,
                trial_id=trial.trial_id,
                treatment=trial.treatment,
                source=ObservationSource.GENERATED_ANALYSIS_FIXTURE,
                status=TreatmentDeliveryStatus.DELIVERED,
                delivered_before_outcome=True,
                current_state_equivalence_sha256=current_state_equivalence_sha256,
                current_duties_sha256=current_duties_sha256,
                carrier_content_sha256=canonical_content_sha256(
                    {
                        "kind": "generated-continuity-carrier",
                        "history_slot_id": block.history_slot_id,
                        "treatment": trial.treatment.value,
                    }
                ),
                provider_call_count=0,
            )
            deliveries.append(delivery)
            observations.append(
                ContinuityObservation(
                    manifest_content_sha256=selected_manifest.content_sha256,
                    plan_content_sha256=selected_plan.content_sha256,
                    block_id=block.block_id,
                    trial_id=trial.trial_id,
                    treatment=trial.treatment,
                    source=ObservationSource.GENERATED_ANALYSIS_FIXTURE,
                    delivery_content_sha256=delivery.content_sha256,
                    history_snapshot_sha256=block.history_snapshot_sha256,
                    event_schedule_sha256=block.event_schedule_sha256,
                    logical_budget_sha256=trial.logical_budget_sha256,
                    model_condition_sha256=selected_manifest.model_condition.content_sha256,
                    failure_kind=ContinuityFailureKind.NONE,
                    continuity_failure=_fixture_failure(
                        history_class=block.history_class,
                        repetition=block.repetition,
                        treatment=trial.treatment,
                    ),
                    ineligibility_reason=None,
                    study_outcome_eligible=False,
                    provider_call_count=0,
                    input_token_count=0,
                    output_token_count=0,
                    maximum_input_tokens_in_one_call=0,
                    maximum_output_tokens_in_one_call=0,
                    spend_currency=None,
                    spend_microunits=0,
                    task_reward_mutation_count=0,
                )
            )

    return ProviderFreeFixtureEvidence(
        deliveries=tuple(deliveries),
        observations=tuple(observations),
    )


def _fixture_failure(
    *,
    history_class: ContinuityHistoryClass,
    repetition: int,
    treatment: ContinuityTreatment,
) -> bool:
    if history_class is ContinuityHistoryClass.H1_STABLE_INSPECTED:
        return treatment is ContinuityTreatment.CURRENT_ACTOR_VIEW and repetition <= 8
    if treatment is ContinuityTreatment.CURRENT_ACTOR_VIEW:
        return True
    return repetition <= 8
