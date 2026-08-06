# ABOUTME: Tests executable identities for the preregistered three-arm program-necessity study.
# ABOUTME: Proves exact lineage evidence and fresh replication prevent lucky-family gate opening.

from __future__ import annotations

import hashlib

import pytest
from pydantic import ValidationError

from aec_bench.contracts.evaluation_plane import EvaluationPlanRef
from aec_bench.contracts.harness_instance import HarnessBudget
from aec_bench.contracts.harness_kernel import canonical_content_sha256
from aec_bench.contracts.program_proposal.candidate import ProgramCandidateRef
from aec_bench.contracts.program_proposal.study import MatchedCandidateEvidenceRef, MatchedEvaluationCoordinate
from aec_bench.contracts.program_proposal.types import CandidateEvidenceKind, OptimizationSplit, ProgramCandidateKind
from aec_bench.contracts.run_bundle import TaskSnapshotRef
from aec_bench.meta_harness.program_necessity import (
    ProgramComplexityDerivationRef,
    ProgramComplexityEvidence,
    ProgramNecessityArm,
    ProgramNecessityArmTemplateRef,
    ProgramNecessityDesign,
    ProgramNecessityExecutionScheduleRef,
    ProgramNecessityFamilyPlan,
    ProgramNecessityLineageCandidateRef,
    ProgramNecessityLineagePlan,
    ProgramNecessityLineageRole,
    ProgramNecessityMeasurementPolicy,
    ProgramNecessityMechanism,
    ProgramNecessityMissingDataPolicy,
    ProgramNecessityObservation,
    ProgramNecessityOpeningPolicy,
    ProgramNecessityPreregistration,
    ProgramNecessityProblemViewRef,
    ProgramNecessityStudyPlan,
    ProgramNecessityStudyRef,
    ProgramTopologyProfile,
    ShamMatchAttestation,
    build_program_necessity_family_result,
    evaluate_program_necessity_gate,
    evaluate_program_necessity_study,
)
from aec_bench.meta_harness.task_snapshot import graph_hidden_task_snapshot_sha256


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _budget() -> HarnessBudget:
    return HarnessBudget(
        max_parallelism=2,
        max_total_attempts=3,
        max_agent_turns=30,
        max_tool_calls=60,
        max_context_tokens=120_000,
        max_runtime_seconds=1_800,
        max_tokens=150_000,
        max_cost_usd=2.0,
    )


def _evaluation_plan() -> EvaluationPlanRef:
    return EvaluationPlanRef(
        plan_id="program-necessity-evaluation",
        evaluation_generation="phase9.1b",
        content_sha256=_sha("program-necessity-evaluation"),
    )


def _arm_templates(family_id: str) -> tuple[ProgramNecessityArmTemplateRef, ...]:
    return tuple(
        ProgramNecessityArmTemplateRef(
            template_id=f"{family_id}.{arm.value}.template",
            arm=arm,
            candidate_kind=(
                ProgramCandidateKind.INCUMBENT
                if arm is ProgramNecessityArm.MONOLITHIC
                else ProgramCandidateKind.PROPOSAL
            ),
            template_artifact_sha256=_sha(f"{family_id}.{arm.value}.template"),
        )
        for arm in ProgramNecessityArm
    )


def _candidate(
    family_id: str,
    lineage_index: int,
    template: ProgramNecessityArmTemplateRef,
) -> ProgramNecessityLineageCandidateRef:
    candidate_id = f"{family_id}.lineage-{lineage_index}.{template.arm.value}"
    incumbent = template.arm is ProgramNecessityArm.MONOLITHIC
    return ProgramNecessityLineageCandidateRef(
        arm=template.arm,
        template_ref_sha256=template.content_sha256,
        candidate=ProgramCandidateRef(
            candidate_id=candidate_id,
            kind=(ProgramCandidateKind.INCUMBENT if incumbent else ProgramCandidateKind.PROPOSAL),
            candidate_artifact_sha256=_sha(f"{candidate_id}.artifact"),
            generation_coordinate_id=(None if incumbent else f"{candidate_id}.generation"),
        ),
    )


def _complexity(
    candidate: ProgramCandidateRef,
    *,
    input_token_mass: int = 10_000,
    source_scope_sha256: str | None = None,
) -> ProgramComplexityEvidence:
    budget = _budget()
    return ProgramComplexityEvidence(
        candidate=candidate,
        derivation=ProgramComplexityDerivationRef(
            derivation_id=f"{candidate.candidate_id}.complexity",
            candidate_artifact_sha256=candidate.candidate_artifact_sha256,
            program_graph_sha256=_sha(f"{candidate.candidate_id}.graph"),
            source_scope_sha256=source_scope_sha256 or _sha(f"{candidate.candidate_id}.sources"),
            aggregate_budget_sha256=canonical_content_sha256(
                budget.model_dump(mode="json"),
            ),
            measurement_policy_sha256=_sha("complexity-measurement-policy"),
            derivation_receipt_sha256=_sha(
                f"{candidate.candidate_id}.complexity-receipt",
            ),
            derived_from_actual_artifacts=True,
        ),
        node_count=3,
        model_invocation_count=3,
        aggregate_budget=budget,
        input_token_mass=input_token_mass,
        context_duplication_tokens=2_000,
        finalizer_sha256=_sha("fixed-finalizer"),
        output_contract_sha256=_sha("fixed-output-contract"),
        topology=ProgramTopologyProfile(
            edge_count=2,
            max_depth=3,
            max_width=1,
            max_fan_in=1,
            max_fan_out=1,
        ),
    )


def _lineage(
    family_id: str,
    lineage_index: int,
    templates: tuple[ProgramNecessityArmTemplateRef, ...],
    *,
    role: ProgramNecessityLineageRole,
) -> ProgramNecessityLineagePlan:
    world_lineage_id = _sha(f"{family_id}.world.{lineage_index}")
    snapshot = TaskSnapshotRef(
        task_id=f"{family_id}.task.{lineage_index}",
        definition_sha256=_sha(f"{family_id}.definition.{lineage_index}"),
        package_sha256=_sha(f"{family_id}.package.{lineage_index}"),
    )
    candidates = tuple(_candidate(family_id, lineage_index, template) for template in templates)
    seeds = (10_000 + lineage_index,)
    coordinates = tuple(
        MatchedEvaluationCoordinate(
            coordinate_id=(f"{family_id}.lineage-{lineage_index}.seed-{seed}.rep-{repetition}"),
            task_id=snapshot.task_id,
            task_revision=snapshot.definition_sha256,
            split=OptimizationSplit.DEVELOPMENT,
            world_lineage_id=world_lineage_id,
            seed=seed,
            repetition=repetition,
        )
        for seed in seeds
        for repetition in range(2)
    )
    candidate_sha256s = tuple(candidate.candidate.content_sha256 for candidate in candidates)
    coordinate_sha256s = tuple(coordinate.content_sha256 for coordinate in coordinates)
    schedule = ProgramNecessityExecutionScheduleRef(
        schedule_id=f"{family_id}.lineage-{lineage_index}.schedule",
        schedule_sha256=_sha(f"{family_id}.lineage-{lineage_index}.schedule"),
        kernel_sha256=_sha("fixed-kernel"),
        fixed_harness_sha256=_sha("fixed-h0"),
        evaluation_plan_ref=_evaluation_plan(),
        world_lineage_id=world_lineage_id,
        candidate_ref_sha256s=candidate_sha256s,
        coordinate_sha256s=coordinate_sha256s,
    )
    study = ProgramNecessityStudyRef(
        study_id=f"{family_id}.lineage-{lineage_index}.study",
        study_sha256=_sha(f"{family_id}.lineage-{lineage_index}.study"),
        execution_schedule_ref_sha256=schedule.content_sha256,
        evaluation_plan_ref=_evaluation_plan(),
        world_lineage_id=world_lineage_id,
        candidate_ref_sha256s=candidate_sha256s,
        coordinate_sha256s=coordinate_sha256s,
    )
    sham = next(candidate.candidate for candidate in candidates if candidate.arm is ProgramNecessityArm.SHAM)
    structural = next(
        candidate.candidate for candidate in candidates if candidate.arm is ProgramNecessityArm.STRUCTURAL
    )
    source_scope_sha256 = _sha(f"{family_id}.lineage-{lineage_index}.sources")
    return ProgramNecessityLineagePlan(
        lineage_plan_id=f"{family_id}.lineage-{lineage_index}",
        world_lineage_id=world_lineage_id,
        role=role,
        task_snapshot=snapshot,
        problem_view=ProgramNecessityProblemViewRef(
            problem_id=f"{family_id}.problem.{lineage_index}",
            problem_view_sha256=_sha(f"{family_id}.problem.{lineage_index}"),
            task_id=snapshot.task_id,
            task_revision=snapshot.definition_sha256,
            public_task_snapshot_sha256=graph_hidden_task_snapshot_sha256(
                snapshot,
            ),
            fixed_harness_projection_sha256=_sha("fixed-h0-projection"),
        ),
        candidate_refs=candidates,
        evaluation_seeds=seeds,
        repetitions_per_seed=2,
        coordinates=coordinates,
        execution_schedule_ref=schedule,
        study_ref=study,
        sham_match=ShamMatchAttestation(
            attestation_id=f"{family_id}.lineage-{lineage_index}.sham-match",
            sham_evidence=_complexity(
                sham,
                source_scope_sha256=source_scope_sha256,
            ),
            structural_evidence=_complexity(
                structural,
                input_token_mass=10_250,
                source_scope_sha256=source_scope_sha256,
            ),
            max_input_token_mass_relative_delta=0.05,
            max_context_duplication_relative_delta=0.05,
            topology_match_required=True,
            matched=True,
        ),
    )


def _family(
    index: int,
    *,
    mechanism: ProgramNecessityMechanism | None = None,
) -> ProgramNecessityFamilyPlan:
    family_id = f"family.{index}"
    templates = _arm_templates(family_id)
    return ProgramNecessityFamilyPlan(
        family_id=family_id,
        mechanism=mechanism or tuple(ProgramNecessityMechanism)[index],
        arm_templates=templates,
        lineage_plans=tuple(
            _lineage(
                family_id,
                lineage,
                templates,
                role=(
                    ProgramNecessityLineageRole.REPLICATION if lineage == 3 else ProgramNecessityLineageRole.DEVELOPMENT
                ),
            )
            for lineage in range(4)
        ),
        expected_structural_direction="positive",
        preregistered=True,
    )


def _preregistration(
    families: tuple[ProgramNecessityFamilyPlan, ...] | None = None,
) -> ProgramNecessityPreregistration:
    return ProgramNecessityPreregistration(
        preregistration_id="program-necessity.phase9.1b",
        kernel_sha256=_sha("fixed-kernel"),
        fixed_harness_sha256=_sha("fixed-h0"),
        evaluation_plan_ref=_evaluation_plan(),
        monitor_policy_sha256=_sha("standing-monitor-policy"),
        monitor_cycle_plan_sha256=_sha("standing-monitor-cycle-plan"),
        monitor_instrumentation_sha256=_sha("standing-monitor-instrumentation"),
        family_plans=families or tuple(_family(index) for index in range(6)),
        measurement_policy=ProgramNecessityMeasurementPolicy(),
        missing_data_policy=ProgramNecessityMissingDataPolicy(),
        opening_policy=ProgramNecessityOpeningPolicy(),
        preregistered=True,
    )


def _observations(
    plan: ProgramNecessityFamilyPlan,
    *,
    positive: bool,
    integrity_passed: bool = True,
) -> tuple[ProgramNecessityObservation, ...]:
    observations: list[ProgramNecessityObservation] = []
    utilities = {
        ProgramNecessityArm.MONOLITHIC: 0.40,
        ProgramNecessityArm.SHAM: 0.50,
        ProgramNecessityArm.STRUCTURAL: 0.65 if positive else 0.45,
    }
    for lineage in plan.lineage_plans:
        for coordinate in lineage.coordinates:
            for arm in ProgramNecessityArm:
                candidate = lineage.candidate_for(arm)
                evidence = MatchedCandidateEvidenceRef(
                    evidence_id=(f"{lineage.lineage_plan_id}.{coordinate.coordinate_id}.{arm.value}"),
                    candidate_id=candidate.candidate_id,
                    coordinate_sha256=coordinate.content_sha256,
                    kind=CandidateEvidenceKind.TRIAL_RECORD,
                    trial_record_sha256=_sha(
                        f"{lineage.lineage_plan_id}.{coordinate.coordinate_id}.{arm.value}.trial",
                    ),
                    evaluation_outcome_sha256=_sha(
                        f"{lineage.lineage_plan_id}.{coordinate.coordinate_id}.{arm.value}.outcome",
                    ),
                    evidence_complete=True,
                    integrity_passed=integrity_passed,
                )
                observations.append(
                    ProgramNecessityObservation(
                        observation_id=evidence.evidence_id,
                        family_id=plan.family_id,
                        world_lineage_id=lineage.world_lineage_id,
                        lineage_plan_sha256=lineage.content_sha256,
                        arm=arm,
                        candidate=candidate,
                        study_ref_sha256=lineage.study_ref.content_sha256,
                        evaluation_plan_ref=_evaluation_plan(),
                        matched_evidence_ref=evidence,
                        utility=utilities[arm],
                        validity_passed=True,
                        integrity_passed=integrity_passed,
                    ),
                )
    return tuple(observations)


def test_family_uses_arm_templates_and_exact_lineage_specific_candidates() -> None:
    plan = _family(0)

    assert set(template.arm for template in plan.arm_templates) == set(
        ProgramNecessityArm,
    )
    assert len(plan.development_lineages) == 3
    assert plan.replication_lineage.role is ProgramNecessityLineageRole.REPLICATION
    assert (
        len(
            {lineage.candidate_for(ProgramNecessityArm.STRUCTURAL).content_sha256 for lineage in plan.lineage_plans},
        )
        == 4
    )
    assert "monolithic_candidate" not in type(plan).model_fields

    original = plan.lineage_plans[1]
    candidate_refs = plan.lineage_plans[0].candidate_refs
    candidate_sha256s = tuple(candidate.candidate.content_sha256 for candidate in candidate_refs)
    schedule = ProgramNecessityExecutionScheduleRef(
        schedule_id=original.execution_schedule_ref.schedule_id,
        schedule_sha256=original.execution_schedule_ref.schedule_sha256,
        kernel_sha256=original.execution_schedule_ref.kernel_sha256,
        fixed_harness_sha256=(original.execution_schedule_ref.fixed_harness_sha256),
        evaluation_plan_ref=original.execution_schedule_ref.evaluation_plan_ref,
        world_lineage_id=original.world_lineage_id,
        candidate_ref_sha256s=candidate_sha256s,
        coordinate_sha256s=tuple(coordinate.content_sha256 for coordinate in original.coordinates),
    )
    study = ProgramNecessityStudyRef(
        study_id=original.study_ref.study_id,
        study_sha256=original.study_ref.study_sha256,
        execution_schedule_ref_sha256=schedule.content_sha256,
        evaluation_plan_ref=original.study_ref.evaluation_plan_ref,
        world_lineage_id=original.world_lineage_id,
        candidate_ref_sha256s=candidate_sha256s,
        coordinate_sha256s=tuple(coordinate.content_sha256 for coordinate in original.coordinates),
    )
    sham = next(candidate.candidate for candidate in candidate_refs if candidate.arm is ProgramNecessityArm.SHAM)
    structural = next(
        candidate.candidate for candidate in candidate_refs if candidate.arm is ProgramNecessityArm.STRUCTURAL
    )
    source_scope_sha256 = _sha(f"{original.lineage_plan_id}.sources")
    reused_lineage = ProgramNecessityLineagePlan(
        lineage_plan_id=original.lineage_plan_id,
        world_lineage_id=original.world_lineage_id,
        role=original.role,
        task_snapshot=original.task_snapshot,
        problem_view=original.problem_view,
        candidate_refs=candidate_refs,
        evaluation_seeds=original.evaluation_seeds,
        repetitions_per_seed=original.repetitions_per_seed,
        coordinates=original.coordinates,
        execution_schedule_ref=schedule,
        study_ref=study,
        sham_match=ShamMatchAttestation(
            attestation_id=original.sham_match.attestation_id,
            sham_evidence=_complexity(
                sham,
                source_scope_sha256=source_scope_sha256,
            ),
            structural_evidence=_complexity(
                structural,
                input_token_mass=10_250,
                source_scope_sha256=source_scope_sha256,
            ),
            max_input_token_mass_relative_delta=0.05,
            max_context_duplication_relative_delta=0.05,
            topology_match_required=True,
            matched=True,
        ),
    )
    with pytest.raises(ValidationError, match="lineage candidates must be unique"):
        ProgramNecessityFamilyPlan(
            family_id=plan.family_id,
            mechanism=plan.mechanism,
            arm_templates=plan.arm_templates,
            lineage_plans=(
                plan.lineage_plans[0],
                reused_lineage,
                *plan.lineage_plans[2:],
            ),
            expected_structural_direction="positive",
            preregistered=True,
        )


def test_lineage_plan_binds_task_view_candidates_schedule_study_and_coordinates() -> None:
    lineage = _family(0).lineage_plans[0]
    assert lineage.problem_view.task_revision == lineage.task_snapshot.definition_sha256
    assert lineage.execution_schedule_ref.candidate_ref_sha256s == tuple(
        sorted(candidate.candidate.content_sha256 for candidate in lineage.candidate_refs),
    )
    assert lineage.study_ref.execution_schedule_ref_sha256 == (lineage.execution_schedule_ref.content_sha256)

    wrong_view = lineage.model_dump(mode="json", exclude={"content_sha256"})
    wrong_view["problem_view"]["task_revision"] = _sha("unrelated-task")
    wrong_view["problem_view"].pop("content_sha256")
    with pytest.raises(ValidationError, match="problem view does not bind"):
        ProgramNecessityLineagePlan.model_validate(wrong_view)

    missing_coordinate = lineage.model_dump(
        mode="json",
        exclude={"content_sha256"},
    )
    missing_coordinate["coordinates"].pop()
    with pytest.raises(ValidationError, match="exact seed and repetition"):
        ProgramNecessityLineagePlan.model_validate(missing_coordinate)

    unrelated_study = lineage.model_dump(
        mode="json",
        exclude={"content_sha256"},
    )
    unrelated_study["study_ref"]["execution_schedule_ref_sha256"] = _sha(
        "another-schedule",
    )
    unrelated_study["study_ref"].pop("content_sha256")
    with pytest.raises(ValidationError, match="study does not bind"):
        ProgramNecessityLineagePlan.model_validate(unrelated_study)


def test_complexity_evidence_requires_artifact_derived_provenance() -> None:
    lineage = _family(0).lineage_plans[0]
    evidence = lineage.sham_match.sham_evidence
    assert evidence.derivation.derived_from_actual_artifacts is True
    assert evidence.derivation.candidate_artifact_sha256 == (evidence.candidate.candidate_artifact_sha256)

    forged_budget = evidence.model_dump(mode="json", exclude={"content_sha256"})
    forged_budget["derivation"]["aggregate_budget_sha256"] = _sha("other-budget")
    forged_budget["derivation"].pop("content_sha256")
    with pytest.raises(ValidationError, match="actual aggregate budget"):
        ProgramComplexityEvidence.model_validate(forged_budget)

    claimed_only = evidence.model_dump(mode="json", exclude={"content_sha256"})
    claimed_only["derivation"]["derived_from_actual_artifacts"] = False
    claimed_only["derivation"].pop("content_sha256")
    with pytest.raises(ValidationError):
        ProgramComplexityEvidence.model_validate(claimed_only)


def test_sham_match_requires_the_same_source_scope_and_measurement_policy() -> None:
    match = _family(0).lineage_plans[0].sham_match

    wrong_scope = match.model_dump(mode="json", exclude={"content_sha256"})
    wrong_scope["structural_evidence"]["derivation"]["source_scope_sha256"] = _sha(
        "other-source-scope",
    )
    wrong_scope["structural_evidence"]["derivation"].pop("content_sha256")
    wrong_scope["structural_evidence"].pop("content_sha256")
    with pytest.raises(ValidationError, match="source scope"):
        ShamMatchAttestation.model_validate(wrong_scope)

    wrong_policy = match.model_dump(mode="json", exclude={"content_sha256"})
    wrong_policy["structural_evidence"]["derivation"]["measurement_policy_sha256"] = _sha(
        "other-measurement-policy",
    )
    wrong_policy["structural_evidence"]["derivation"].pop("content_sha256")
    wrong_policy["structural_evidence"].pop("content_sha256")
    with pytest.raises(ValidationError, match="measurement policy"):
        ShamMatchAttestation.model_validate(wrong_policy)


def test_observation_must_bind_exact_lineage_candidate_study_and_evaluation() -> None:
    plan = _family(0)
    observations = list(_observations(plan, positive=True))
    first = observations[0]
    forged = first.model_dump(mode="json", exclude={"content_sha256"})
    forged["candidate"]["candidate_artifact_sha256"] = _sha("unrelated-candidate")
    forged["candidate"].pop("content_sha256")
    observations[0] = ProgramNecessityObservation.model_validate(forged)

    with pytest.raises(ValueError, match="exact lineage candidate"):
        build_program_necessity_family_result(
            plan=plan,
            observations=tuple(observations),
        )

    observations = list(_observations(plan, positive=True))
    wrong_evaluation = observations[0].model_dump(
        mode="json",
        exclude={"content_sha256"},
    )
    wrong_evaluation["evaluation_plan_ref"]["content_sha256"] = _sha(
        "unrelated-evaluation",
    )
    observations[0] = ProgramNecessityObservation.model_validate(
        wrong_evaluation,
    )
    with pytest.raises(ValueError, match="exact lineage study and evaluation"):
        build_program_necessity_family_result(
            plan=plan,
            observations=tuple(observations),
        )


def test_family_qualification_uses_lineage_means_not_execution_count() -> None:
    plan = _family(0)
    result = build_program_necessity_family_result(
        plan=plan,
        observations=_observations(plan, positive=True),
    )

    assert result.qualifies is True
    assert len(result.lineage_contrasts) == 4
    assert all(contrast.structural_residual > 0 for contrast in result.lineage_contrasts)
    assert result.development_direction_consistent is True
    assert result.replication_direction_confirmed is True

    null_result = build_program_necessity_family_result(
        plan=plan,
        observations=_observations(plan, positive=False),
    )
    assert null_result.qualifies is False
    assert null_result.evidence_valid is True


def test_preregistration_freezes_six_families_24_lineages_and_all_planes() -> None:
    preregistration = _preregistration()
    assert len(preregistration.family_plans) == 6
    assert sum(len(family.lineage_plans) for family in preregistration.family_plans) == 24
    assert preregistration.kernel_sha256 == _sha("fixed-kernel")
    assert preregistration.fixed_harness_sha256 == _sha("fixed-h0")
    assert preregistration.evaluation_plan_ref == _evaluation_plan()
    assert preregistration.monitor_instrumentation_sha256 == _sha(
        "standing-monitor-instrumentation",
    )
    assert preregistration.missing_data_policy.imputation == "forbidden"
    assert preregistration.measurement_policy.within_lineage_aggregation == "arithmetic_mean_across_seed_repetitions"

    missing_family = preregistration.model_dump(
        mode="json",
        exclude={"content_sha256"},
    )
    missing_family["family_plans"].pop()
    with pytest.raises(ValidationError):
        ProgramNecessityPreregistration.model_validate(missing_family)

    with pytest.raises(ValidationError, match="kernel, H0, or evaluation"):
        ProgramNecessityPreregistration(
            preregistration_id=preregistration.preregistration_id,
            kernel_sha256=_sha("other-kernel"),
            fixed_harness_sha256=preregistration.fixed_harness_sha256,
            evaluation_plan_ref=preregistration.evaluation_plan_ref,
            monitor_policy_sha256=preregistration.monitor_policy_sha256,
            monitor_cycle_plan_sha256=(preregistration.monitor_cycle_plan_sha256),
            monitor_instrumentation_sha256=(preregistration.monitor_instrumentation_sha256),
            family_plans=preregistration.family_plans,
            measurement_policy=preregistration.measurement_policy,
            missing_data_policy=preregistration.missing_data_policy,
            opening_policy=preregistration.opening_policy,
            preregistered=True,
        )


def test_historical_program_necessity_v1_hashes_remain_stable() -> None:
    preregistration = _preregistration()
    results = tuple(
        build_program_necessity_family_result(
            plan=family,
            observations=_observations(family, positive=index < 2),
        )
        for index, family in enumerate(preregistration.family_plans)
    )
    gate = evaluate_program_necessity_gate(
        plan=preregistration,
        family_results=results,
    )

    assert preregistration.content_sha256 == ("7992dee06cf76f3f6d637ddd94b6268501dfdd706b88a7c14af4c7705f5417d7")
    assert results[0].content_sha256 == ("02dfe93de9cc36719e99ae0b69427ed1ce69846ac6bc7a554aa5d7f5ad17f9b8")
    assert gate.content_sha256 == ("b490721442daea83b131229e0892774112283fae0b14431cdb15cf3272cbd334")


def test_program_necessity_design_owns_cardinality_and_gate_thresholds() -> None:
    families = tuple(
        ProgramNecessityFamilyPlan.model_validate(
            {
                **_family(index).model_dump(
                    mode="python",
                    exclude={"content_sha256", "lineage_plans"},
                ),
                "lineage_plans": (
                    _family(index).development_lineages[0],
                    _family(index).replication_lineage,
                ),
            },
        )
        for index in range(2)
    )
    measurement = ProgramNecessityMeasurementPolicy()
    missing_data = ProgramNecessityMissingDataPolicy()
    design = ProgramNecessityDesign(
        family_count=2,
        development_lineages_per_family=1,
        replication_lineages_per_family=1,
        required_qualifying_family_count=2,
        required_distinct_mechanism_count=2,
        required_mechanisms=tuple(family.mechanism for family in families),
        measurement_policy_sha256=measurement.content_sha256,
        missing_data_policy_sha256=missing_data.content_sha256,
    )
    plan = ProgramNecessityStudyPlan(
        study_id="program-necessity.generic-design",
        kernel_sha256=_sha("fixed-kernel"),
        fixed_harness_sha256=_sha("fixed-h0"),
        evaluation_plan_ref=_evaluation_plan(),
        monitor_policy_sha256=_sha("standing-monitor-policy"),
        monitor_cycle_plan_sha256=_sha("standing-monitor-cycle-plan"),
        monitor_instrumentation_sha256=_sha("standing-monitor-instrumentation"),
        design=design,
        family_plans=families,
        measurement_policy=measurement,
        missing_data_policy=missing_data,
        preregistered=True,
    )
    results = tuple(
        build_program_necessity_family_result(
            plan=family,
            observations=_observations(family, positive=True),
        )
        for family in families
    )

    outcome = evaluate_program_necessity_study(
        plan=plan,
        family_results=results,
    )

    assert outcome.gate_open is True
    assert outcome.qualifying_family_ids == ("family.0", "family.1")
    assert len(outcome.family_results) == 2


def test_program_necessity_design_requires_every_replication_lineage_to_confirm() -> None:
    source = _family(0)
    second_replication = ProgramNecessityLineagePlan.model_validate(
        {
            **source.development_lineages[1].model_dump(
                mode="python",
                exclude={"content_sha256", "role"},
            ),
            "role": ProgramNecessityLineageRole.REPLICATION,
        },
    )
    family = ProgramNecessityFamilyPlan.model_validate(
        {
            **source.model_dump(
                mode="python",
                exclude={"content_sha256", "lineage_plans"},
            ),
            "lineage_plans": (
                source.development_lineages[0],
                second_replication,
                source.replication_lineage,
            ),
        },
    )
    observations = tuple(
        ProgramNecessityObservation.model_validate(
            {
                **observation.model_dump(
                    mode="python",
                    exclude={"content_sha256", "utility"},
                ),
                "utility": (
                    0.45
                    if observation.world_lineage_id == second_replication.world_lineage_id
                    and observation.arm is ProgramNecessityArm.STRUCTURAL
                    else observation.utility
                ),
            },
        )
        for observation in _observations(family, positive=True)
    )

    result = build_program_necessity_family_result(
        plan=family,
        observations=observations,
    )

    assert result.evidence_valid is True
    assert result.development_direction_consistent is True
    assert result.replication_direction_confirmed is False
    assert result.qualifies is False


def test_gate_requires_two_qualifying_families_from_different_mechanisms() -> None:
    preregistration = _preregistration()
    results = tuple(
        build_program_necessity_family_result(
            plan=family,
            observations=_observations(
                family,
                positive=index < 2,
            ),
        )
        for index, family in enumerate(preregistration.family_plans)
    )

    opened = evaluate_program_necessity_gate(
        plan=preregistration,
        family_results=results,
    )
    assert opened.gate_open is True
    assert opened.qualifying_family_ids == ("family.0", "family.1")
    assert len(opened.family_results) == 6

    invalid_results = tuple(
        build_program_necessity_family_result(
            plan=family,
            observations=_observations(
                family,
                positive=index < 2,
                integrity_passed=index != 5,
            ),
        )
        for index, family in enumerate(preregistration.family_plans)
    )
    closed = evaluate_program_necessity_gate(
        plan=preregistration,
        family_results=invalid_results,
    )
    assert closed.gate_open is False
    assert closed.all_evidence_valid is False
