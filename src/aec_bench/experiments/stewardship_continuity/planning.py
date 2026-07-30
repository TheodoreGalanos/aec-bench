# ABOUTME: Builds the frozen provider-free manifest and counterbalanced continuity plan.
# ABOUTME: Binds the study design to the certified pump-station package and rule versions.

from __future__ import annotations

from aec_bench.contracts.harness_kernel import canonical_content_sha256
from aec_bench.evaluation.stewardship import STEWARDSHIP_EVALUATION_SCHEMA_VERSION
from aec_bench.experiments.stewardship_continuity.contracts import (
    ContinuityBlock,
    ContinuityExecutionKind,
    ContinuityHistoryClass,
    ContinuityLogicalBudget,
    ContinuityModelCondition,
    ContinuityStudyManifest,
    ContinuityStudyPhase,
    ContinuityStudyPlan,
    ContinuityTreatment,
    ContinuityTrial,
    EvaluationWindow,
    continuity_block_id,
    continuity_trial_id,
    logical_budget_sha256,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.reference_package_reader import (
    EXPECTED_MANIFEST_CONTENT_ID,
    EXPECTED_PACKAGE_CONTENT_ID,
    load_reference_package,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_models import (
    PUMP_STATION_AUTHORITY_POLICY_VERSION,
    PUMP_STATION_RECEIPT_VERSION,
    PUMP_STATION_TRANSITION_RULE_VERSION,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_session import (
    PUMP_STATION_PROJECTION_POLICY_ID,
    PUMP_STATION_TASK_WORLD_ID,
    PUMP_STATION_TOOL_NAMES,
)

CONTINUITY_STUDY_ID = "asw-first-stewardship-continuity.v1"
ASW4A_STUDY_GENERATION_ID = "asw-4a-provider-free-analysis-fixture.v1"
CONTINUITY_EVENT_SCHEDULE_REVISION = "pump-station-continuity-event-schedule.v1"
CONTINUITY_VERIFIER_REVISION = "pump-station-stewardship-replay-verifier.v1"


def build_provider_free_manifest() -> ContinuityStudyManifest:
    """Build the ASW-4A design freeze with no provider or outcome authority."""

    package = load_reference_package()
    logical_budget = ContinuityLogicalBudget()
    model_condition = ContinuityModelCondition(
        execution_kind=ContinuityExecutionKind.ANALYSIS_FIXTURE,
        provider_id=None,
        model_id=None,
        adapter_id=None,
        model_configuration_sha256=canonical_content_sha256(
            {
                "kind": "generated-provider-free-analysis-condition.v1",
                "study_generation_id": ASW4A_STUDY_GENERATION_ID,
            }
        ),
    )
    return ContinuityStudyManifest(
        study_id=CONTINUITY_STUDY_ID,
        study_generation_id=ASW4A_STUDY_GENERATION_ID,
        phase=ContinuityStudyPhase.ANALYSIS_FIXTURE,
        charter_revision="ASW-0C-3",
        task_world_id=PUMP_STATION_TASK_WORLD_ID,
        profile_id=package.profile_id,
        generation_id=package.generation_id,
        package_content_id=EXPECTED_PACKAGE_CONTENT_ID,
        promotion_manifest_content_id=EXPECTED_MANIFEST_CONTENT_ID,
        receipt_version=PUMP_STATION_RECEIPT_VERSION,
        authority_policy_version=PUMP_STATION_AUTHORITY_POLICY_VERSION,
        transition_rule_version=PUMP_STATION_TRANSITION_RULE_VERSION,
        projection_policy_id=PUMP_STATION_PROJECTION_POLICY_ID,
        evaluation_schema_version=STEWARDSHIP_EVALUATION_SCHEMA_VERSION,
        event_schedule_revision=CONTINUITY_EVENT_SCHEDULE_REVISION,
        verifier_revision=CONTINUITY_VERIFIER_REVISION,
        harness_configuration_sha256=canonical_content_sha256(
            {
                "kind": "pump-station-continuity-harness.v1",
                "task_world_id": PUMP_STATION_TASK_WORLD_ID,
                "projection_policy_id": PUMP_STATION_PROJECTION_POLICY_ID,
                "tool_names": PUMP_STATION_TOOL_NAMES,
            }
        ),
        treatment_delivery_configuration_sha256=canonical_content_sha256(
            {
                "kind": "pump-station-continuity-treatment-delivery.v1",
                "treatments": [treatment.value for treatment in ContinuityTreatment],
                "same_current_state_required": True,
                "same_current_duties_required": True,
            }
        ),
        model_condition=model_condition,
        provider_authorization=None,
        history_classes=tuple(ContinuityHistoryClass),
        treatments=tuple(ContinuityTreatment),
        logical_budget=logical_budget,
        study_outcomes_allowed=False,
    )


def build_continuity_plan(
    manifest: ContinuityStudyManifest,
) -> ContinuityStudyPlan:
    """Expand the frozen design into 32 paired, counterbalanced blocks."""

    selected = ContinuityStudyManifest.model_validate(
        manifest.model_dump(mode="json"),
    )
    budget_sha256 = logical_budget_sha256(selected.logical_budget)
    blocks: list[ContinuityBlock] = []

    for repetition in range(1, selected.blocks_per_history + 1):
        evaluation_window = _evaluation_window(repetition)
        ordered_treatments = _ordered_treatments(repetition)
        for history_class in ContinuityHistoryClass:
            sequence_index = len(blocks) + 1
            history_slot_id = f"{history_class.value}-{repetition:02d}"
            history_snapshot_sha256 = canonical_content_sha256(
                {
                    "kind": "planned-provider-free-continuity-history.v1",
                    "study_generation_id": selected.study_generation_id,
                    "history_slot_id": history_slot_id,
                    "history_class": history_class.value,
                }
            )
            event_schedule_sha256 = canonical_content_sha256(
                {
                    "kind": selected.event_schedule_revision,
                    "study_generation_id": selected.study_generation_id,
                    "history_slot_id": history_slot_id,
                    "evaluation_window": evaluation_window.value,
                }
            )
            block_id = continuity_block_id(
                study_id=selected.study_id,
                study_generation_id=selected.study_generation_id,
                sequence_index=sequence_index,
                repetition=repetition,
                history_class=history_class,
                history_slot_id=history_slot_id,
                evaluation_window=evaluation_window,
                history_snapshot_sha256=history_snapshot_sha256,
                event_schedule_sha256=event_schedule_sha256,
            )
            trials = tuple(
                _build_trial(
                    manifest=selected,
                    block_id=block_id,
                    sequence_index=sequence_index,
                    repetition=repetition,
                    history_class=history_class,
                    history_slot_id=history_slot_id,
                    treatment=treatment,
                    order_index=order_index,
                    evaluation_window=evaluation_window,
                    budget_sha256=budget_sha256,
                )
                for order_index, treatment in enumerate(
                    ordered_treatments,
                    start=1,
                )
            )
            blocks.append(
                ContinuityBlock(
                    block_id=block_id,
                    study_id=selected.study_id,
                    study_generation_id=selected.study_generation_id,
                    sequence_index=sequence_index,
                    repetition=repetition,
                    history_class=history_class,
                    history_slot_id=history_slot_id,
                    evaluation_window=evaluation_window,
                    history_snapshot_sha256=history_snapshot_sha256,
                    event_schedule_sha256=event_schedule_sha256,
                    trials=trials,
                )
            )

    block_tuple = tuple(blocks)
    return ContinuityStudyPlan(
        manifest_content_sha256=selected.content_sha256,
        study_id=selected.study_id,
        study_generation_id=selected.study_generation_id,
        blocks=block_tuple,
        trials=tuple(trial for block in block_tuple for trial in block.trials),
    )


def _evaluation_window(repetition: int) -> EvaluationWindow:
    if repetition % 2:
        return EvaluationWindow.THREE_DIAGNOSTIC_PERIODS
    return EvaluationWindow.FOUR_DIAGNOSTIC_PERIODS


def _ordered_treatments(
    repetition: int,
) -> tuple[ContinuityTreatment, ContinuityTreatment]:
    if ((repetition - 1) // 2) % 2 == 0:
        return (
            ContinuityTreatment.CURRENT_ACTOR_VIEW,
            ContinuityTreatment.STRUCTURED_HANDOVER,
        )
    return (
        ContinuityTreatment.STRUCTURED_HANDOVER,
        ContinuityTreatment.CURRENT_ACTOR_VIEW,
    )


def _build_trial(
    *,
    manifest: ContinuityStudyManifest,
    block_id: str,
    sequence_index: int,
    repetition: int,
    history_class: ContinuityHistoryClass,
    history_slot_id: str,
    treatment: ContinuityTreatment,
    order_index: int,
    evaluation_window: EvaluationWindow,
    budget_sha256: str,
) -> ContinuityTrial:
    trial_id = continuity_trial_id(
        study_id=manifest.study_id,
        study_generation_id=manifest.study_generation_id,
        block_id=block_id,
        sequence_index=sequence_index,
        repetition=repetition,
        history_class=history_class,
        history_slot_id=history_slot_id,
        treatment=treatment,
        order_index=order_index,
        evaluation_window=evaluation_window,
        logical_budget_sha256=budget_sha256,
    )
    return ContinuityTrial(
        trial_id=trial_id,
        study_id=manifest.study_id,
        study_generation_id=manifest.study_generation_id,
        block_id=block_id,
        sequence_index=sequence_index,
        repetition=repetition,
        history_class=history_class,
        history_slot_id=history_slot_id,
        treatment=treatment,
        order_index=order_index,
        evaluation_window=evaluation_window,
        evaluation_window_seconds=evaluation_window.seconds,
        logical_budget_sha256=budget_sha256,
    )
