# ABOUTME: Tests evidence-blind proposal scheduling and fail-closed candidate selection.
# ABOUTME: Proves proposal studies cannot prune candidates, launder failures, or invoke repair.

from __future__ import annotations

import hashlib
import inspect
import math

import pytest
from pydantic import ValidationError

from aec_bench.contracts.authority import OperatorRole, operator_authority_for
from aec_bench.contracts.evaluation_outcome import (
    CandidatePlaneCost,
    CriticPlaneCost,
    EvaluationCostBreakdown,
    EvaluationDisposition,
    EvaluationOutcome,
    IntegrityCheck,
    IntegrityEvaluation,
    ResourceCost,
    UtilityEvaluation,
    ValidityEvaluation,
)
from aec_bench.contracts.evaluation_refs import CriticRef, CriticRole
from aec_bench.contracts.harness_instance import HarnessBudget, HarnessInstanceRef
from aec_bench.contracts.harness_kernel import KernelRef
from aec_bench.contracts.program_proposal.candidate import (
    CandidateGenerationCoordinate,
    CandidateGenerationManifest,
    ProgramCandidateRef,
)
from aec_bench.contracts.program_proposal.freeze import ProposalFreeze
from aec_bench.contracts.program_proposal.problem import DecompositionLeakageAudit, DecompositionProblemView
from aec_bench.contracts.program_proposal.study import (
    DecompositionOptimizationCycle,
    MatchedCandidateEvidenceRef,
    MatchedEvaluationCoordinate,
)
from aec_bench.contracts.program_proposal.types import (
    CandidateEvidenceKind,
    OptimizationDisposition,
    OptimizationSplit,
    ProgramCandidateKind,
)
from aec_bench.experimentation.proposals import decomposition_optimization
from aec_bench.experimentation.proposals.decomposition_optimization import (
    DevelopmentSelectionResult,
    EvidenceOutcomeBinding,
    FrozenSelectionRule,
    OptimizationExperimentError,
    build_decomposition_execution_schedule,
    complete_decomposition_optimization_cycle,
    complete_program_candidate_study,
    load_decomposition_optimization_result,
)
from tests.support.evaluation_regimes import fake_regime_ref


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _budget() -> HarnessBudget:
    return HarnessBudget(
        max_parallelism=2,
        max_total_attempts=8,
        max_agent_turns=32,
        max_tool_calls=64,
        max_context_tokens=300_000,
        max_runtime_seconds=3_600,
        max_tokens=300_000,
        max_cost_usd=1.25,
    )


def _view() -> DecompositionProblemView:
    return DecompositionProblemView.model_validate(
        {
            "problem_id": "problem.drainage-01",
            "task_id": "drainage-01",
            "task_revision": _sha("task-revision"),
            "public_task_snapshot_sha256": _sha("public-task"),
            "public_instruction": "Review the drainage package.",
            "public_sources": [
                {
                    "source_id": "source.report",
                    "opaque_handle": "public-source:report",
                    "media_type": "text/plain",
                    "byte_size": 10,
                    "source_sha256": _sha("report"),
                }
            ],
            "output_contract": {
                "schema_version": "aecbench.output-completion-contract.v1",
                "output_path": "answer.md",
                "format": "markdown_final_fenced_json",
                "required_top_level_keys": ["decision"],
                "require_single_final_json_block": True,
            },
            "fixed_harness": {
                "kernel_ref": {"kernel_id": "fixed-kernel", "version": "1"},
                "harness_policy_sha256": _sha("h0-policy"),
                "capability_ids": ["context.public", "tool.read"],
                "aggregate_budget": _budget().model_dump(mode="json"),
            },
            "public_domain_id": "civil",
            "public_task_family_id": "drainage-review",
        }
    )


def _proposal(candidate_id: str, index: int) -> ProgramCandidateRef:
    return ProgramCandidateRef(
        candidate_id=candidate_id,
        kind=ProgramCandidateKind.PROPOSAL,
        candidate_artifact_sha256=_sha(f"artifact:{candidate_id}"),
        generation_coordinate_id=f"generation.{index}",
    )


def _incumbent(*, artifact_label: str = "incumbent") -> ProgramCandidateRef:
    return ProgramCandidateRef(
        candidate_id="candidate.incumbent",
        kind=ProgramCandidateKind.INCUMBENT,
        candidate_artifact_sha256=_sha(artifact_label),
    )


def _selection_rule() -> FrozenSelectionRule:
    return FrozenSelectionRule(
        rule_id="rule.minimum-delta",
        minimum_utility_delta=0.05,
    )


def _development_critic(
    *,
    regime_label: str = "phase-9",
) -> CriticRef:
    return CriticRef(
        regime=fake_regime_ref(regime_id="regime.phase-9", label=regime_label),
        critic_id="critic.development",
        role=CriticRole.DEVELOPMENT,
    )


def _freeze() -> ProposalFreeze:
    view = _view()
    manifest = CandidateGenerationManifest(
        manifest_id="manifest.phase-9",
        problem_view_sha256=view.content_sha256,
        proposal_policy_sha256=_sha("proposal-policy"),
        policy_checkpoint_sha256=_sha("checkpoint"),
        selection_policy_sha256=_selection_rule().content_sha256,
        expected_candidate_count=2,
        coordinates=(
            CandidateGenerationCoordinate(
                coordinate_id="generation.1",
                candidate_id="candidate.1",
                seed=101,
            ),
            CandidateGenerationCoordinate(
                coordinate_id="generation.2",
                candidate_id="candidate.2",
                seed=202,
            ),
        ),
        stopping_policy_sha256=_sha("stop-after-two"),
    )
    return ProposalFreeze(
        freeze_id="freeze.phase-9",
        evaluation_regime_ref=fake_regime_ref(regime_id="regime.phase-9", label="phase-9"),
        structural_split_sha256=_sha("structural-split"),
        selected_structural_item_sha256=_sha("selected-structural-item"),
        selected_review_lineage_id=_sha("selected-review-lineage"),
        fixed_harness_ref=HarnessInstanceRef(instance_id="compiled-h0"),
        operator_authority=operator_authority_for(
            "optimizer.proposer",
            OperatorRole.PERFORMANCE_OPTIMIZATION,
        ),
        split=OptimizationSplit.DEVELOPMENT,
        leakage_audit=DecompositionLeakageAudit(
            audit_id="audit.phase-9",
            audited_input_sha256=_sha("builder-input"),
            audit_policy_sha256=_sha("leakage-policy"),
            passed=True,
            finding_codes=(),
            problem_view_sha256=view.content_sha256,
        ),
        problem_view=view,
        candidate_manifest=manifest,
        proposal_policy_sha256=manifest.proposal_policy_sha256,
        policy_checkpoint_sha256=manifest.policy_checkpoint_sha256,
        realized_candidates=(
            _proposal("candidate.1", 1),
            _proposal("candidate.2", 2),
        ),
        proposal_set_closed=True,
        late_candidates_permitted=False,
    )


def _coordinates() -> tuple[MatchedEvaluationCoordinate, ...]:
    return (
        MatchedEvaluationCoordinate(
            coordinate_id="evaluation.1",
            task_id="drainage-01",
            task_revision=_sha("task-revision"),
            split=OptimizationSplit.DEVELOPMENT,
            review_lineage_id=_sha("selected-review-lineage"),
            seed=11,
            repetition=0,
        ),
        MatchedEvaluationCoordinate(
            coordinate_id="evaluation.2",
            task_id="drainage-01",
            task_revision=_sha("task-revision"),
            split=OptimizationSplit.DEVELOPMENT,
            review_lineage_id=_sha("selected-review-lineage"),
            seed=22,
            repetition=0,
        ),
    )


def _schedule(
    *,
    incumbent: ProgramCandidateRef | None = None,
    coordinates: tuple[MatchedEvaluationCoordinate, ...] | None = None,
):
    freeze = _freeze()
    return build_decomposition_execution_schedule(
        schedule_id="schedule.phase-9",
        proposal_freeze=freeze,
        incumbent_candidate=incumbent or _incumbent(),
        coordinates=coordinates or _coordinates(),
        kernel_ref=freeze.problem_view.fixed_harness.kernel_ref,
        fixed_harness_ref=freeze.fixed_harness_ref,
        evaluation_regime_ref=freeze.evaluation_regime_ref,
        aggregate_budget=freeze.problem_view.fixed_harness.aggregate_budget,
    )


def _resource() -> ResourceCost:
    return ResourceCost(
        provider_calls=0,
        tokens=0,
        provider_cost_usd=0.0,
        wall_time_seconds=0.0,
    )


def _costs() -> EvaluationCostBreakdown:
    resource = _resource()
    return EvaluationCostBreakdown(
        candidate=CandidatePlaneCost(
            proposal=resource,
            execution=resource,
        ),
        critic_plane=CriticPlaneCost(
            development=resource,
            acceptance=resource,
            red_team=resource,
            monitor=resource,
            human_audit=resource,
        ),
    )


def _outcome(
    schedule,
    candidate: ProgramCandidateRef,
    coordinate: MatchedEvaluationCoordinate,
    *,
    utility: float,
    kind: CandidateEvidenceKind = CandidateEvidenceKind.TRIAL_RECORD,
    integrity: bool = True,
    complete: bool = True,
) -> EvaluationOutcome:
    label = f"{candidate.candidate_id}:{coordinate.coordinate_id}"
    if not integrity:
        return EvaluationOutcome(
            candidate_sha256=candidate.candidate_artifact_sha256,
            evidence_set_sha256=_sha(f"evidence-set:{label}"),
            integrity=IntegrityEvaluation.create(
                checks=(
                    IntegrityCheck(
                        check_id="runtime-integrity",
                        passed=False,
                        reasons=("integrity evidence failed",),
                    ),
                )
            ),
            costs=_costs(),
            disposition=EvaluationDisposition.EXPERIMENT_ERROR,
            promotion_eligible=False,
            reasons=("integrity evidence failed",),
        )
    if not complete:
        return EvaluationOutcome(
            candidate_sha256=candidate.candidate_artifact_sha256,
            evidence_set_sha256=_sha(f"evidence-set:{label}"),
            integrity=IntegrityEvaluation.create(checks=(IntegrityCheck(check_id="runtime-integrity", passed=True),)),
            validity=ValidityEvaluation(
                verifier_completed=False,
                output_parseable=False,
                schema_valid=False,
                output_contract_valid=False,
                valid=False,
                reasons=("evaluation evidence incomplete",),
            ),
            costs=_costs(),
            disposition=EvaluationDisposition.EXPERIMENT_ERROR,
            promotion_eligible=False,
            reasons=("evaluation evidence incomplete",),
        )
    if kind is not CandidateEvidenceKind.TRIAL_RECORD:
        return EvaluationOutcome(
            candidate_sha256=candidate.candidate_artifact_sha256,
            evidence_set_sha256=_sha(f"evidence-set:{label}"),
            integrity=IntegrityEvaluation.create(checks=(IntegrityCheck(check_id="runtime-integrity", passed=True),)),
            validity=ValidityEvaluation(
                verifier_completed=True,
                output_parseable=False,
                schema_valid=False,
                output_contract_valid=False,
                valid=False,
                reasons=(f"{kind.value} prevented a valid output",),
            ),
            utility=UtilityEvaluation.zero(),
            costs=_costs(),
            disposition=EvaluationDisposition.REJECT,
            promotion_eligible=False,
            reasons=(f"{kind.value} prevented a valid output",),
        )
    return EvaluationOutcome(
        candidate_sha256=candidate.candidate_artifact_sha256,
        evidence_set_sha256=_sha(f"evidence-set:{label}"),
        integrity=IntegrityEvaluation.create(checks=(IntegrityCheck(check_id="runtime-integrity", passed=True),)),
        validity=ValidityEvaluation(
            verifier_completed=True,
            output_parseable=True,
            schema_valid=True,
            output_contract_valid=True,
            valid=True,
        ),
        utility=UtilityEvaluation(
            normalized_utility=utility,
            reward=utility,
            solved=utility >= 0.5,
            acceptance_threshold_met=utility >= 0.5,
        ),
        costs=_costs(),
        disposition=(EvaluationDisposition.ACCEPT if utility >= 0.5 else EvaluationDisposition.REJECT),
        promotion_eligible=utility >= 0.5,
    )


def _evidence(
    candidate: ProgramCandidateRef,
    coordinate: MatchedEvaluationCoordinate,
    *,
    kind: CandidateEvidenceKind = CandidateEvidenceKind.TRIAL_RECORD,
    complete: bool = True,
    integrity: bool = True,
) -> MatchedCandidateEvidenceRef:
    label = f"{candidate.candidate_id}:{coordinate.coordinate_id}"
    return MatchedCandidateEvidenceRef(
        evidence_id=f"evidence.{label}",
        candidate_id=candidate.candidate_id,
        coordinate_sha256=coordinate.content_sha256,
        kind=kind,
        trial_record_sha256=(_sha(f"trial:{label}") if kind is CandidateEvidenceKind.TRIAL_RECORD else None),
        evidence_complete=complete,
        integrity_passed=integrity,
    )


def _evidence_bundle(
    schedule,
    values: dict[str, float],
    *,
    kind_by_candidate: dict[str, CandidateEvidenceKind] | None = None,
    failed_integrity_pair: tuple[str, str] | None = None,
    incomplete_pair: tuple[str, str] | None = None,
) -> tuple[
    tuple[MatchedCandidateEvidenceRef, ...],
    tuple[EvidenceOutcomeBinding, ...],
]:
    evidence: list[MatchedCandidateEvidenceRef] = []
    outcomes: list[EvidenceOutcomeBinding] = []
    for assignment in schedule.assignments:
        pair = (
            assignment.candidate.candidate_id,
            assignment.coordinate.coordinate_id,
        )
        kind = (kind_by_candidate or {}).get(
            assignment.candidate.candidate_id,
            CandidateEvidenceKind.TRIAL_RECORD,
        )
        integrity = pair != failed_integrity_pair
        complete = pair != incomplete_pair
        outcome = _outcome(
            schedule,
            assignment.candidate,
            assignment.coordinate,
            utility=values[assignment.candidate.candidate_id],
            kind=kind,
            integrity=integrity,
            complete=complete,
        )
        reference = _evidence(
            assignment.candidate,
            assignment.coordinate,
            kind=kind,
            complete=complete,
            integrity=integrity,
        )
        evidence.append(reference)
        outcomes.append(
            EvidenceOutcomeBinding(
                evidence_id=reference.evidence_id,
                evidence_sha256=reference.content_sha256,
                outcome=outcome,
            )
        )
    return tuple(evidence), tuple(outcomes)


def _complete_evidence(schedule) -> tuple[MatchedCandidateEvidenceRef, ...]:
    evidence, _ = _evidence_bundle(
        schedule,
        {
            "candidate.incumbent": 0.5,
            "candidate.1": 0.6,
            "candidate.2": 0.4,
        },
    )
    return evidence


def test_schedule_is_complete_evidence_blind_cross_product() -> None:
    schedule = _schedule()

    expected_pairs = {
        (candidate_id, coordinate.content_sha256)
        for candidate_id in ("candidate.incumbent", "candidate.1", "candidate.2")
        for coordinate in _coordinates()
    }
    assert {
        (assignment.candidate.candidate_id, assignment.coordinate.content_sha256) for assignment in schedule.assignments
    } == expected_pairs
    assert len(schedule.assignments) == 6
    assert not {
        "evidence_refs",
        "evaluation_outcome",
        "incumbent_valid",
        "score",
        "utility",
    } & set(type(schedule).model_fields)


def test_known_valid_incumbent_still_schedules_every_frozen_proposal() -> None:
    schedule = _schedule(incumbent=_incumbent(artifact_label="known-valid-incumbent"))

    assert {assignment.candidate.candidate_id for assignment in schedule.assignments} == {
        "candidate.incumbent",
        "candidate.1",
        "candidate.2",
    }
    parameters = inspect.signature(build_decomposition_execution_schedule).parameters
    assert not {"incumbent_valid", "outcomes", "scores", "utilities"} & set(parameters)


def test_schedule_is_order_invariant_and_rejects_binding_drift() -> None:
    schedule = _schedule()
    reordered = _schedule(coordinates=tuple(reversed(_coordinates())))
    assert reordered.content_sha256 == schedule.content_sha256

    freeze = _freeze()
    common = {
        "schedule_id": "schedule.phase-9",
        "proposal_freeze": freeze,
        "incumbent_candidate": _incumbent(),
        "coordinates": _coordinates(),
        "kernel_ref": freeze.problem_view.fixed_harness.kernel_ref,
        "fixed_harness_ref": freeze.fixed_harness_ref,
        "evaluation_regime_ref": freeze.evaluation_regime_ref,
        "aggregate_budget": freeze.problem_view.fixed_harness.aggregate_budget,
    }
    for field, value, message in (
        ("kernel_ref", KernelRef(kernel_id="wrong-kernel", version="1"), "kernel"),
        ("fixed_harness_ref", HarnessInstanceRef(instance_id="wrong-h0"), "fixed H0"),
        (
            "evaluation_regime_ref",
            fake_regime_ref(regime_id="other"),
            "evaluation regime",
        ),
        ("aggregate_budget", HarnessBudget(), "aggregate budget"),
    ):
        with pytest.raises(ValidationError, match=message):
            build_decomposition_execution_schedule(**{**common, field: value})


def test_schedule_rejects_task_or_split_coordinate_drift() -> None:
    coordinate = _coordinates()[0]
    for field, value, message in (
        ("task_id", "other-task", "task"),
        ("task_revision", _sha("other-task-revision"), "task"),
        ("split", OptimizationSplit.TRAINING, "split"),
        ("review_lineage_id", _sha("other-review-lineage"), "review lineage"),
    ):
        mutated = MatchedEvaluationCoordinate.model_validate(
            {
                **coordinate.model_dump(mode="json", exclude={"content_sha256"}),
                field: value,
            }
        )
        with pytest.raises(ValidationError, match=message):
            _schedule(coordinates=(mutated,))


def test_schedule_rejects_coordinate_id_alias_for_the_same_semantic_run() -> None:
    original = _coordinates()[0]
    alias = MatchedEvaluationCoordinate.model_validate(
        {
            **original.model_dump(mode="json", exclude={"content_sha256"}),
            "coordinate_id": "evaluation.alias",
        }
    )

    with pytest.raises(ValidationError, match="semantic identities must be unique"):
        _schedule(coordinates=(original, alias))


def test_study_completion_rejects_missing_duplicate_or_mutated_evidence_before_utility() -> None:
    schedule = _schedule()
    evidence = _complete_evidence(schedule)
    study = complete_program_candidate_study(
        study_id="study.phase-9",
        schedule=schedule,
        evidence_refs=evidence,
    )
    assert len(study.evidence_refs) == len(schedule.assignments)

    with pytest.raises(ValidationError, match="exact candidate-coordinate coverage"):
        complete_program_candidate_study(
            study_id="study.phase-9",
            schedule=schedule,
            evidence_refs=evidence[:-1],
        )
    with pytest.raises(ValidationError, match="matched evidence ids must be unique"):
        complete_program_candidate_study(
            study_id="study.phase-9",
            schedule=schedule,
            evidence_refs=(*evidence[:-1], evidence[0]),
        )
    mutated = MatchedCandidateEvidenceRef.model_validate(
        {
            **evidence[0].model_dump(mode="json", exclude={"content_sha256"}),
            "coordinate_sha256": _sha("unknown-coordinate"),
        }
    )
    with pytest.raises(ValidationError, match="exact candidate-coordinate coverage"):
        complete_program_candidate_study(
            study_id="study.phase-9",
            schedule=schedule,
            evidence_refs=(mutated, *evidence[1:]),
        )


def test_compile_rejection_requires_no_trial_and_can_never_win() -> None:
    schedule = _schedule()
    evidence, outcomes = _evidence_bundle(
        schedule,
        {
            "candidate.incumbent": 0.5,
            "candidate.1": 0.0,
            "candidate.2": 0.4,
        },
        kind_by_candidate={
            "candidate.1": CandidateEvidenceKind.COMPILE_REJECTION,
        },
    )
    study = complete_program_candidate_study(
        study_id="study.compile-rejection",
        schedule=schedule,
        evidence_refs=evidence,
    )
    result = complete_decomposition_optimization_cycle(
        cycle_id="cycle.compile-rejection",
        schedule=schedule,
        study=study,
        outcome_bindings=outcomes,
        selection_rule=_selection_rule(),
        development_critic=_development_critic(),
    )

    rejected = next(
        comparison
        for comparison in result.cycle.comparisons
        if comparison.challenger_candidate.candidate_id == "candidate.1"
    )
    assert rejected.disposition is OptimizationDisposition.REJECT
    assert all(reference.trial_record_sha256 is None for reference in rejected.challenger_evidence_refs)

    dishonest_evidence, dishonest_outcomes = _evidence_bundle(
        schedule,
        {
            "candidate.incumbent": 0.5,
            "candidate.1": 0.9,
            "candidate.2": 0.4,
        },
    )
    dishonest_evidence = tuple(
        MatchedCandidateEvidenceRef.model_validate(
            {
                **reference.model_dump(mode="json", exclude={"content_sha256"}),
                "kind": CandidateEvidenceKind.COMPILE_REJECTION,
                "trial_record_sha256": None,
            }
        )
        if reference.candidate_id == "candidate.1"
        else reference
        for reference in dishonest_evidence
    )
    dishonest_study = complete_program_candidate_study(
        study_id="study.dishonest-compile-rejection",
        schedule=schedule,
        evidence_refs=dishonest_evidence,
    )
    dishonest_outcomes_by_id = {binding.evidence_id: binding for binding in dishonest_outcomes}
    rebound_outcomes = tuple(
        EvidenceOutcomeBinding(
            evidence_id=reference.evidence_id,
            evidence_sha256=reference.content_sha256,
            outcome=dishonest_outcomes_by_id[reference.evidence_id].outcome,
        )
        for reference in dishonest_evidence
    )
    with pytest.raises(
        OptimizationExperimentError,
        match="non-trial evidence requires a zero-utility rejection",
    ):
        complete_decomposition_optimization_cycle(
            cycle_id="cycle.invalid-rejection",
            schedule=schedule,
            study=dishonest_study,
            outcome_bindings=rebound_outcomes,
            selection_rule=_selection_rule(),
            development_critic=_development_critic(),
        )


def test_selection_is_deterministic_bound_and_order_invariant() -> None:
    schedule = _schedule()
    evidence, outcomes = _evidence_bundle(
        schedule,
        {
            "candidate.incumbent": 0.5,
            "candidate.1": 0.8,
            "candidate.2": 0.8,
        },
    )
    study = complete_program_candidate_study(
        study_id="study.selection",
        schedule=schedule,
        evidence_refs=tuple(reversed(evidence)),
    )
    rule = _selection_rule()
    first = complete_decomposition_optimization_cycle(
        cycle_id="cycle.selection",
        schedule=schedule,
        study=study,
        outcome_bindings=outcomes,
        selection_rule=rule,
        development_critic=_development_critic(),
    )
    second = complete_decomposition_optimization_cycle(
        cycle_id="cycle.selection",
        schedule=schedule,
        study=study,
        outcome_bindings=tuple(reversed(outcomes)),
        selection_rule=rule,
        development_critic=_development_critic(),
    )

    assert first.content_sha256 == second.content_sha256
    assert first.cycle.disposition is OptimizationDisposition.DEVELOPMENT_SELECTED
    assert first.cycle.selected_candidate_id == "candidate.1"
    dispositions = {
        comparison.challenger_candidate.candidate_id: comparison.disposition for comparison in first.cycle.comparisons
    }
    assert dispositions == {
        "candidate.1": OptimizationDisposition.DEVELOPMENT_SELECTED,
        "candidate.2": OptimizationDisposition.ABSTAIN,
    }

    mismatched = EvidenceOutcomeBinding(
        evidence_id=outcomes[0].evidence_id,
        evidence_sha256=_sha("mutated-evidence"),
        outcome=outcomes[0].outcome,
    )
    with pytest.raises(
        OptimizationExperimentError,
        match="does not bind exact study evidence",
    ):
        complete_decomposition_optimization_cycle(
            cycle_id="cycle.mismatched",
            schedule=schedule,
            study=study,
            outcome_bindings=(mismatched, *outcomes[1:]),
            selection_rule=rule,
            development_critic=_development_critic(),
        )


def test_produced_result_is_explicitly_development_selected_and_cannot_be_acceptance_evidence() -> None:
    schedule = _schedule()
    evidence, outcomes = _evidence_bundle(
        schedule,
        {
            "candidate.incumbent": 0.5,
            "candidate.1": 0.8,
            "candidate.2": 0.8,
        },
    )
    study = complete_program_candidate_study(
        study_id="study.development-selection",
        schedule=schedule,
        evidence_refs=evidence,
    )
    critic = _development_critic()

    result = complete_decomposition_optimization_cycle(
        cycle_id="cycle.development-selection",
        schedule=schedule,
        study=study,
        outcome_bindings=outcomes,
        selection_rule=_selection_rule(),
        development_critic=critic,
    )

    assert isinstance(result, DevelopmentSelectionResult)
    assert result.selection_regime.development_critic == critic
    assert result.selection_regime.evaluation_regime_ref == schedule.evaluation_regime_ref
    assert result.selection_regime.selection_rule_sha256 == _selection_rule().content_sha256
    assert result.selection_regime.split is OptimizationSplit.DEVELOPMENT
    assert result.optimization_result.cycle.disposition is OptimizationDisposition.DEVELOPMENT_SELECTED
    assert {
        comparison.disposition
        for comparison in result.optimization_result.cycle.comparisons
        if comparison.selected_candidate_id == "candidate.1"
    } == {OptimizationDisposition.DEVELOPMENT_SELECTED}
    assert all(
        comparison.disposition is not OptimizationDisposition.ACCEPT
        for comparison in result.optimization_result.cycle.comparisons
    )
    assert result.promotion_eligible is False
    with pytest.raises(ValidationError):
        EvaluationOutcome.model_validate(result.model_dump(mode="json"))
    assert load_decomposition_optimization_result(result.model_dump_json()) == result


def test_development_selection_rejects_non_development_critic_or_generation() -> None:
    schedule = _schedule()
    evidence, outcomes = _evidence_bundle(
        schedule,
        {
            "candidate.incumbent": 0.5,
            "candidate.1": 0.8,
            "candidate.2": 0.4,
        },
    )
    study = complete_program_candidate_study(
        study_id="study.critic-binding",
        schedule=schedule,
        evidence_refs=evidence,
    )
    common = {
        "cycle_id": "cycle.critic-binding",
        "schedule": schedule,
        "study": study,
        "outcome_bindings": outcomes,
        "selection_rule": _selection_rule(),
    }
    acceptance_critic = CriticRef(
        regime=schedule.evaluation_regime_ref,
        critic_id="critic.acceptance",
        role=CriticRole.ACCEPTANCE,
    )

    with pytest.raises(OptimizationExperimentError, match="development critic"):
        complete_decomposition_optimization_cycle(
            **common,
            development_critic=acceptance_critic,
        )
    with pytest.raises(OptimizationExperimentError, match="evaluation regime"):
        complete_decomposition_optimization_cycle(
            **common,
            development_critic=_development_critic(
                regime_label="different-regime",
            ),
        )


def test_outcomes_bind_the_exact_candidate_artifact() -> None:
    schedule = _schedule()
    evidence, outcomes = _evidence_bundle(
        schedule,
        {
            "candidate.incumbent": 0.5,
            "candidate.1": 0.6,
            "candidate.2": 0.4,
        },
    )
    original_binding = outcomes[0]
    mutated_outcome = EvaluationOutcome.model_validate(
        {
            **original_binding.outcome.model_dump(
                mode="json",
                exclude={"content_sha256"},
            ),
            "candidate_sha256": _sha("wrong-candidate-artifact"),
        }
    )
    mutated_bindings = tuple(
        EvidenceOutcomeBinding(
            evidence_id=original_binding.evidence_id,
            evidence_sha256=original_binding.evidence_sha256,
            outcome=mutated_outcome,
        )
        if binding.evidence_id == original_binding.evidence_id
        else binding
        for binding in outcomes
    )
    study = complete_program_candidate_study(
        study_id="study.wrong-candidate-artifact",
        schedule=schedule,
        evidence_refs=evidence,
    )

    with pytest.raises(OptimizationExperimentError, match="exact candidate artifact"):
        complete_decomposition_optimization_cycle(
            cycle_id="cycle.wrong-candidate-artifact",
            schedule=schedule,
            study=study,
            outcome_bindings=mutated_bindings,
            selection_rule=_selection_rule(),
            development_critic=_development_critic(),
        )


def test_abstaining_outcome_cannot_be_promoted_by_its_scalar_utility() -> None:
    schedule = _schedule()
    evidence, outcomes = _evidence_bundle(
        schedule,
        {
            "candidate.incumbent": 0.3,
            "candidate.1": 0.9,
            "candidate.2": 0.2,
        },
    )
    target = next(binding for binding in outcomes if binding.evidence_id.startswith("evidence.candidate.1:"))
    abstaining_outcome = EvaluationOutcome.model_validate(
        {
            **target.outcome.model_dump(
                mode="json",
                exclude={"content_sha256"},
            ),
            "disposition": EvaluationDisposition.ABSTAIN,
            "promotion_eligible": False,
        }
    )
    outcomes = tuple(
        EvidenceOutcomeBinding(
            evidence_id=target.evidence_id,
            evidence_sha256=target.evidence_sha256,
            outcome=abstaining_outcome,
        )
        if binding.evidence_id == target.evidence_id
        else binding
        for binding in outcomes
    )
    study = complete_program_candidate_study(
        study_id="study.abstaining-outcome",
        schedule=schedule,
        evidence_refs=evidence,
    )
    result = complete_decomposition_optimization_cycle(
        cycle_id="cycle.abstaining-outcome",
        schedule=schedule,
        study=study,
        outcome_bindings=outcomes,
        selection_rule=_selection_rule(),
        development_critic=_development_critic(),
    )

    assert result.cycle.disposition is OptimizationDisposition.ABSTAIN
    assert result.cycle.selected_candidate_id is None
    assert all(comparison.disposition is not OptimizationDisposition.ACCEPT for comparison in result.cycle.comparisons)


def test_integrity_failure_forces_experiment_error_and_blocks_other_acceptance() -> None:
    schedule = _schedule()
    evidence, outcomes = _evidence_bundle(
        schedule,
        {
            "candidate.incumbent": 0.3,
            "candidate.1": 0.9,
            "candidate.2": 0.8,
        },
        failed_integrity_pair=("candidate.1", "evaluation.1"),
    )
    study = complete_program_candidate_study(
        study_id="study.integrity-failure",
        schedule=schedule,
        evidence_refs=evidence,
    )
    result = complete_decomposition_optimization_cycle(
        cycle_id="cycle.integrity-failure",
        schedule=schedule,
        study=study,
        outcome_bindings=outcomes,
        selection_rule=_selection_rule(),
        development_critic=_development_critic(),
    )

    assert result.cycle.disposition is OptimizationDisposition.EXPERIMENT_ERROR
    assert result.cycle.selected_candidate_id is None
    assert all(comparison.disposition is not OptimizationDisposition.ACCEPT for comparison in result.cycle.comparisons)


def test_incomplete_evidence_forces_experiment_error_and_blocks_acceptance() -> None:
    schedule = _schedule()
    evidence, outcomes = _evidence_bundle(
        schedule,
        {
            "candidate.incumbent": 0.3,
            "candidate.1": 0.9,
            "candidate.2": 0.8,
        },
        incomplete_pair=("candidate.1", "evaluation.1"),
    )
    study = complete_program_candidate_study(
        study_id="study.incomplete",
        schedule=schedule,
        evidence_refs=evidence,
    )
    result = complete_decomposition_optimization_cycle(
        cycle_id="cycle.incomplete",
        schedule=schedule,
        study=study,
        outcome_bindings=outcomes,
        selection_rule=_selection_rule(),
        development_critic=_development_critic(),
    )

    assert result.cycle.disposition is OptimizationDisposition.EXPERIMENT_ERROR
    assert result.cycle.selected_candidate_id is None
    assert all(comparison.disposition is not OptimizationDisposition.ACCEPT for comparison in result.cycle.comparisons)


def test_nonfinite_or_duplicate_outcome_bindings_fail_closed() -> None:
    with pytest.raises(ValidationError):
        UtilityEvaluation(
            normalized_utility=math.nan,
            reward=0.0,
            solved=False,
            acceptance_threshold_met=False,
        )

    schedule = _schedule()
    evidence, outcomes = _evidence_bundle(
        schedule,
        {
            "candidate.incumbent": 0.5,
            "candidate.1": 0.6,
            "candidate.2": 0.4,
        },
    )
    study = complete_program_candidate_study(
        study_id="study.duplicate-outcome",
        schedule=schedule,
        evidence_refs=evidence,
    )
    with pytest.raises(
        OptimizationExperimentError,
        match="outcome evidence ids must be unique",
    ):
        complete_decomposition_optimization_cycle(
            cycle_id="cycle.duplicate-outcome",
            schedule=schedule,
            study=study,
            outcome_bindings=(*outcomes, outcomes[0]),
            selection_rule=_selection_rule(),
            development_critic=_development_critic(),
        )


def test_post_hoc_selection_rule_substitution_fails_before_outcome_resolution() -> None:
    schedule = _schedule()
    evidence, _ = _evidence_bundle(
        schedule,
        {
            "candidate.incumbent": 0.5,
            "candidate.1": 0.6,
            "candidate.2": 0.4,
        },
    )
    study = complete_program_candidate_study(
        study_id="study.rule-substitution",
        schedule=schedule,
        evidence_refs=evidence,
    )
    post_hoc_rule = FrozenSelectionRule(
        rule_id="rule.post-hoc",
        minimum_utility_delta=0.0,
    )

    with pytest.raises(
        OptimizationExperimentError,
        match="selection rule does not match the frozen selection policy",
    ):
        complete_decomposition_optimization_cycle(
            cycle_id="cycle.rule-substitution",
            schedule=schedule,
            study=study,
            outcome_bindings=(),
            selection_rule=post_hoc_rule,
            development_critic=_development_critic(),
        )


def test_missing_outcome_is_explicit_experiment_error_without_imputation() -> None:
    schedule = _schedule()
    evidence, outcomes = _evidence_bundle(
        schedule,
        {
            "candidate.incumbent": 0.5,
            "candidate.1": 0.6,
            "candidate.2": 0.4,
        },
    )
    study = complete_program_candidate_study(
        study_id="study.missing-outcome",
        schedule=schedule,
        evidence_refs=evidence,
    )

    with pytest.raises(OptimizationExperimentError) as raised:
        complete_decomposition_optimization_cycle(
            cycle_id="cycle.missing-outcome",
            schedule=schedule,
            study=study,
            outcome_bindings=outcomes[:-1],
            selection_rule=_selection_rule(),
            development_critic=_development_critic(),
        )
    assert raised.value.disposition is OptimizationDisposition.EXPERIMENT_ERROR
    assert "unresolvable evaluation outcome" in str(raised.value)


def test_module_has_no_diagnostic_repair_dependency() -> None:
    imported_modules = {
        value.__name__ for value in vars(decomposition_optimization).values() if inspect.ismodule(value)
    }
    assert (
        not {
            "aec_bench.meta_harness.failure_diagnosis",
            "aec_bench.meta_harness.repair_loop",
            "aec_bench.meta_harness.verifier_guided_repair",
        }
        & imported_modules
    )
    assert "FailureDiagnoser" not in vars(decomposition_optimization)
    assert DecompositionOptimizationCycle is not None
