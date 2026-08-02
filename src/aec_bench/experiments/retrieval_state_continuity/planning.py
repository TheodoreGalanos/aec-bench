# ABOUTME: Builds the frozen retrieval-state study manifest and paired plan.
# ABOUTME: Binds every planned run to the certified world and local temporal corpus.

from __future__ import annotations

import hashlib
import random

from aec_bench.contracts.harness_kernel import canonical_content_sha256
from aec_bench.experiments.retrieval_state_continuity.contracts import (
    ModelExecutionSpecification,
    PlannedTrial,
    RetrievalStudyBudget,
    StudyAnalysisSpecification,
    StudyBlock,
    StudyManifest,
    StudyPhase,
    StudyPlan,
    Treatment,
    TreatmentSpecification,
    study_block_id,
    study_trial_id,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.reference_package_reader import (
    load_reference_package,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.temporal_evidence.corpus import (
    REFERENCE_WORLD_TIME_SECONDS,
    build_reference_temporal_evidence_bundle,
)

_WORLD_HISTORY_SEEDS = (1103, 2207, 3313, 4421, 5527, 6637, 7753, 8861)
_MATERIAL_EVIDENCE_VERSION_ID = "pump-a-delayed-condition-report.v1"
_DEVELOPMENT_QUERY_ROUTES = (
    "pump a obstruction condition report",
    "pump a delayed inspection record",
    "condition inspection obstruction indicator",
)


def build_provider_free_manifest() -> StudyManifest:
    """Build the exact provider-free temporal study specification."""

    package = load_reference_package()
    bundle = build_reference_temporal_evidence_bundle(package, world_branch_id="study-main")
    material = next(item for item in bundle.versions if item.version_id == _MATERIAL_EVIDENCE_VERSION_ID)
    budget = RetrievalStudyBudget()
    analysis = StudyAnalysisSpecification()
    treatment = TreatmentSpecification()
    retrievability_certificate_sha256 = canonical_content_sha256(
        {
            "material_evidence_version_id": material.version_id,
            "acceptable_evidence_version_ids": [material.version_id],
            "development_query_routes": list(_DEVELOPMENT_QUERY_ROUTES),
            "corpus_snapshot_id": bundle.corpus_manifest.content_sha256,
            "retrieval_policy_id": bundle.retrieval_policy.content_sha256,
            "access_policy_id": bundle.access_policy.content_sha256,
            "availability_schedule_id": bundle.availability.content_sha256,
            "budget": budget.model_dump(mode="json"),
            "available_at_seconds": material.available_at_seconds,
            "decision_deadline_seconds": material.available_at_seconds + 3_600,
            "decision_rule_id": "pump-a-obstruction-evidence-decision-rule.v1",
        }
    )
    base_carrier_audit_sha256 = canonical_content_sha256(
        {
            "base_carrier_id": treatment.base_carrier_id,
            "audit": "retrieval-clean",
            "forbidden_content": [
                "pre-handover query",
                "negative result",
                "unresolved search",
                "material target hint",
            ],
            "result": "absent",
        }
    )
    return StudyManifest(
        study_id="retrieval-state-continuity-under-delayed-evidence.v1",
        study_generation_id="retrieval-state-continuity-provider-free-specification.v1",
        phase=StudyPhase.ANALYSIS_FIXTURE,
        profile_id=package.profile_id,
        generation_id=package.generation_id,
        package_content_id=package.package_content_id,
        certification_content_id=package.manifest_content_id,
        corpus_snapshot_id=bundle.corpus_manifest.content_sha256,
        corpus_lineage_id=bundle.lineage.content_sha256,
        retrieval_policy_id=bundle.retrieval_policy.content_sha256,
        access_policy_id=bundle.access_policy.content_sha256,
        availability_schedule_id=bundle.availability.content_sha256,
        branch_policy_id=bundle.branch_policy.content_sha256,
        cost_policy_id=bundle.cost_policy.content_sha256,
        material_evidence_version_id=material.version_id,
        acceptable_evidence_version_ids=(material.version_id,),
        development_query_routes=_DEVELOPMENT_QUERY_ROUTES,
        decision_rule_id="pump-a-obstruction-evidence-decision-rule.v1",
        retrievability_certificate_sha256=retrievability_certificate_sha256,
        base_carrier_audit_sha256=base_carrier_audit_sha256,
        current_actor_view_policy_id="pump-station-current-state.v1",
        verifier_id="pump-station-temporal-evidence-verifier.v1",
        pre_handover_world_time_seconds=REFERENCE_WORLD_TIME_SECONDS,
        evidence_available_at_seconds=material.available_at_seconds,
        decision_deadline_seconds=material.available_at_seconds + 3_600,
        world_history_seeds=_WORLD_HISTORY_SEEDS,
        treatments=tuple(Treatment),
        treatment=treatment,
        budget=budget,
        analysis=analysis,
    )


def build_model_manifest(phase: StudyPhase) -> StudyManifest:
    """Derive one real-model generation without changing the frozen design."""

    if phase not in {StudyPhase.SHAKEDOWN, StudyPhase.CONFIRMATORY}:
        raise ValueError("model manifest phase must be shakedown or confirmatory")
    provider_free = build_provider_free_manifest()
    payload = provider_free.model_dump(mode="json", exclude={"content_sha256"})
    model_execution = ModelExecutionSpecification()
    payload.update(
        {
            "study_generation_id": (
                "retrieval-state-continuity-model-shakedown.v3"
                if phase is StudyPhase.SHAKEDOWN
                else "retrieval-state-continuity-confirmatory.v2"
            ),
            "phase": phase,
            "decision_rule_id": model_execution.decision_rule_id,
            "retrievability_certificate_sha256": canonical_content_sha256(
                {
                    "prior_retrievability_certificate_sha256": (provider_free.retrievability_certificate_sha256),
                    "decision_rule_id": model_execution.decision_rule_id,
                    "admissible_conservative_actions": (model_execution.admissible_conservative_actions),
                    "shakedown_amendment": "permitted-conservative-action-coverage.v1",
                }
            ),
            "model_execution": model_execution,
            "provider_calls_allowed": 24 if phase is StudyPhase.SHAKEDOWN else 768,
            "study_outcomes_allowed": phase is StudyPhase.CONFIRMATORY,
        }
    )
    return StudyManifest.model_validate(payload)


def build_study_plan(manifest: StudyManifest) -> StudyPlan:
    """Expand the frozen specification into balanced adjacent pairs."""

    selected = StudyManifest.model_validate(manifest.model_dump(mode="json"))
    coordinates = [
        (seed, replicate)
        for seed in selected.world_history_seeds
        for replicate in range(1, selected.analysis.model_sampling_replicates_per_history + 1)
    ]
    schedule = random.Random(selected.schedule_seed)
    schedule.shuffle(coordinates)
    first_treatment_by_coordinate: dict[tuple[int, int], Treatment] = {}
    for seed in selected.world_history_seeds:
        assignments = [
            Treatment.RETRIEVAL_STATE_ABSENT,
            Treatment.RETRIEVAL_STATE_ABSENT,
            Treatment.RETRIEVAL_STATE_PRESERVED,
            Treatment.RETRIEVAL_STATE_PRESERVED,
        ]
        history_seed = int.from_bytes(
            hashlib.sha256(f"{selected.schedule_seed}:{seed}".encode()).digest(),
            byteorder="big",
        )
        random.Random(history_seed).shuffle(assignments)
        for replicate, treatment in enumerate(assignments, start=1):
            first_treatment_by_coordinate[(seed, replicate)] = treatment

    blocks: list[StudyBlock] = []
    execution_position = 1
    budget_sha256 = canonical_content_sha256(selected.budget.model_dump(mode="json"))
    for sequence_index, (world_history_seed, sampling_replicate) in enumerate(coordinates, start=1):
        history_snapshot_sha256 = canonical_content_sha256(
            {
                "profile_id": selected.profile_id,
                "package_content_id": selected.package_content_id,
                "world_history_seed": world_history_seed,
                "scenario": "delayed-material-evidence-before-consequential-decision.v1",
            }
        )
        event_schedule_sha256 = canonical_content_sha256(
            {
                "history_snapshot_sha256": history_snapshot_sha256,
                "availability_schedule_id": selected.availability_schedule_id,
                "material_evidence_version_id": selected.material_evidence_version_id,
                "pre_handover_world_time_seconds": selected.pre_handover_world_time_seconds,
                "evidence_available_at_seconds": selected.evidence_available_at_seconds,
                "decision_deadline_seconds": selected.decision_deadline_seconds,
            }
        )
        current_actor_view_sha256 = canonical_content_sha256(
            {
                "history_snapshot_sha256": history_snapshot_sha256,
                "policy_id": selected.current_actor_view_policy_id,
                "projection": "complete-current-actor-view",
            }
        )
        base_carrier_sha256 = canonical_content_sha256(
            {
                "history_snapshot_sha256": history_snapshot_sha256,
                "base_carrier_id": selected.treatment.base_carrier_id,
                "base_carrier_audit_sha256": selected.base_carrier_audit_sha256,
            }
        )
        non_treatment_input_sha256 = canonical_content_sha256(
            {
                "history_snapshot_sha256": history_snapshot_sha256,
                "event_schedule_sha256": event_schedule_sha256,
                "current_actor_view_sha256": current_actor_view_sha256,
                "base_carrier_sha256": base_carrier_sha256,
                "sampling_replicate": sampling_replicate,
                "budget_sha256": budget_sha256,
            }
        )
        block_id = study_block_id(
            manifest_content_sha256=selected.content_sha256,
            sequence_index=sequence_index,
            world_history_seed=world_history_seed,
            sampling_replicate=sampling_replicate,
            history_snapshot_sha256=history_snapshot_sha256,
            event_schedule_sha256=event_schedule_sha256,
        )
        first = first_treatment_by_coordinate[(world_history_seed, sampling_replicate)]
        second = (
            Treatment.RETRIEVAL_STATE_PRESERVED
            if first is Treatment.RETRIEVAL_STATE_ABSENT
            else Treatment.RETRIEVAL_STATE_ABSENT
        )
        trials = tuple(
            _build_trial(
                block_id=block_id,
                treatment=treatment,
                order_index=order_index,
                execution_position=execution_position + order_index - 1,
                budget_sha256=budget_sha256,
            )
            for order_index, treatment in enumerate((first, second), start=1)
        )
        blocks.append(
            StudyBlock(
                block_id=block_id,
                manifest_content_sha256=selected.content_sha256,
                sequence_index=sequence_index,
                world_history_seed=world_history_seed,
                sampling_replicate=sampling_replicate,
                history_snapshot_sha256=history_snapshot_sha256,
                event_schedule_sha256=event_schedule_sha256,
                non_treatment_input_sha256=non_treatment_input_sha256,
                current_actor_view_sha256=current_actor_view_sha256,
                base_carrier_sha256=base_carrier_sha256,
                trials=trials,
            )
        )
        execution_position += 2
    block_tuple = tuple(blocks)
    return StudyPlan(
        manifest_content_sha256=selected.content_sha256,
        schedule_algorithm=selected.schedule_algorithm,
        schedule_seed=selected.schedule_seed,
        blocks=block_tuple,
        trials=tuple(trial for block in block_tuple for trial in block.trials),
    )


def _build_trial(
    *,
    block_id: str,
    treatment: Treatment,
    order_index: int,
    execution_position: int,
    budget_sha256: str,
) -> PlannedTrial:
    trial_id = study_trial_id(
        block_id=block_id,
        treatment=treatment,
        order_index=order_index,
        execution_position=execution_position,
        budget_sha256=budget_sha256,
    )
    return PlannedTrial(
        trial_id=trial_id,
        block_id=block_id,
        treatment=treatment,
        order_index=order_index,
        execution_position=execution_position,
        budget_sha256=budget_sha256,
    )
