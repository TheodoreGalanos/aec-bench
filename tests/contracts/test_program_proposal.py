# ABOUTME: Tests reward-blind proposal views, frozen candidate sets, and matched optimisation studies.
# ABOUTME: Proves program-proposal contracts reject privileged leakage and repair-shaped lifecycle semantics.

from __future__ import annotations

import copy
import hashlib

import pytest
from pydantic import ValidationError

from aec_bench.contracts.authority import OperatorRole, operator_authority_for
from aec_bench.contracts.evaluation_generation.cohort import EvaluationCohortBinding
from aec_bench.contracts.evaluation_plane import CandidateManifestScope, EvaluationPlanRef
from aec_bench.contracts.harness_instance import HarnessBudget
from aec_bench.contracts.harness_kernel import canonical_content_sha256
from aec_bench.contracts.program_proposal.candidate import (
    CandidateGenerationCoordinate,
    CandidateGenerationManifest,
    ProgramCandidateRef,
)
from aec_bench.contracts.program_proposal.freeze import ProposalFreeze
from aec_bench.contracts.program_proposal.problem import (
    DecompositionLeakageAudit,
    DecompositionProblemView,
    PublicSourceRef,
)
from aec_bench.contracts.program_proposal.study import (
    DecompositionOptimizationCycle,
    MatchedCandidateEvidenceRef,
    MatchedEvaluationCoordinate,
    PairedCandidateComparison,
    ProgramCandidateStudy,
)
from aec_bench.contracts.program_proposal.types import (
    CandidateEvidenceKind,
    OptimizationDisposition,
    OptimizationSplit,
    ProgramCandidateKind,
)


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


def _view_payload() -> dict[str, object]:
    return {
        "problem_id": "problem.drainage-01",
        "task_id": "drainage-01",
        "task_revision": _sha("task-revision"),
        "public_task_snapshot_sha256": _sha("public-task-snapshot"),
        "public_instruction": "Review the supplied drainage package and produce the declared response.",
        "public_sources": [
            {
                "source_id": "source.report",
                "opaque_handle": "public-source:report",
                "media_type": "application/pdf",
                "byte_size": 12_345,
                "source_sha256": _sha("source-report"),
            }
        ],
        "output_contract": {
            "schema_version": "aecbench.output-completion-contract.v1",
            "output_path": "answer.md",
            "format": "markdown_final_fenced_json",
            "required_top_level_keys": ["decision", "evidence"],
            "require_single_final_json_block": True,
        },
        "fixed_harness": {
            "kernel_sha256": _sha("kernel"),
            "harness_policy_sha256": _sha("h0-policy"),
            "capability_ids": ["context.public", "tool.read", "tool.write"],
            "aggregate_budget": _budget().model_dump(mode="json"),
        },
        "public_domain_id": "civil",
        "public_task_family_id": "drainage-review",
        "data_gap_boundaries": [
            {
                "boundary_id": "gap.missing-invert",
                "statement": "Missing invert data must be declared rather than inferred.",
            }
        ],
        "authority_boundaries": [
            {
                "boundary_id": "authority.design-change",
                "statement": "The proposal may recommend but cannot approve a design change.",
            }
        ],
    }


def _view() -> DecompositionProblemView:
    return DecompositionProblemView.model_validate(_view_payload())


def _plan_ref(candidate_manifest_sha256: str) -> EvaluationPlanRef:
    return EvaluationPlanRef(
        plan_id="plan.phase-9",
        evaluation_generation="critic-generation-1",
        content_sha256=_sha(f"plan:{candidate_manifest_sha256}"),
    )


def _manifest(view: DecompositionProblemView) -> CandidateGenerationManifest:
    return CandidateGenerationManifest(
        manifest_id="manifest.zero-shot",
        problem_view_sha256=view.content_sha256,
        proposal_policy_sha256=_sha("proposal-policy"),
        policy_checkpoint_sha256=_sha("checkpoint"),
        selection_policy_sha256=_sha("selection-policy"),
        expected_candidate_count=2,
        coordinates=(
            CandidateGenerationCoordinate(
                coordinate_id="proposal-coordinate.1",
                candidate_id="candidate.1",
                seed=101,
            ),
            CandidateGenerationCoordinate(
                coordinate_id="proposal-coordinate.2",
                candidate_id="candidate.2",
                seed=202,
            ),
        ),
        stopping_policy_sha256=_sha("two-candidates-then-stop"),
    )


def _proposal(candidate_id: str, index: int) -> ProgramCandidateRef:
    return ProgramCandidateRef(
        candidate_id=candidate_id,
        kind=ProgramCandidateKind.PROPOSAL,
        candidate_artifact_sha256=_sha(f"proposal:{candidate_id}"),
        generation_coordinate_id=f"proposal-coordinate.{index}",
    )


def _incumbent() -> ProgramCandidateRef:
    return ProgramCandidateRef(
        candidate_id="candidate.incumbent",
        kind=ProgramCandidateKind.INCUMBENT,
        candidate_artifact_sha256=_sha("incumbent-artifact"),
    )


def _audit(view: DecompositionProblemView) -> DecompositionLeakageAudit:
    return DecompositionLeakageAudit(
        audit_id="audit.problem-view",
        audited_input_sha256=_sha("public-builder-input"),
        audit_policy_sha256=_sha("leakage-policy"),
        passed=True,
        finding_codes=(),
        problem_view_sha256=view.content_sha256,
    )


def _freeze() -> ProposalFreeze:
    view = _view()
    manifest = _manifest(view)
    return ProposalFreeze(
        freeze_id="freeze.problem-01",
        evaluation_plan_ref=_plan_ref(manifest.content_sha256),
        evaluation_plan_candidate_manifest_sha256=manifest.content_sha256,
        structural_split_sha256=_sha("structural-split"),
        selected_structural_item_sha256=_sha("selected-structural-item"),
        selected_review_lineage_id=_sha("selected-review-lineage"),
        fixed_harness_sha256=_sha("compiled-h0-host-binding"),
        operator_authority=operator_authority_for(
            "optimizer.zero-shot",
            OperatorRole.PERFORMANCE_OPTIMIZATION,
        ),
        split=OptimizationSplit.DEVELOPMENT,
        leakage_audit=_audit(view),
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


def test_proposal_freeze_can_bind_one_member_of_a_multitask_candidate_scope() -> None:
    view = _view()
    manifest = _manifest(view)
    scope = CandidateManifestScope(
        scope_id="candidate-scope.phase91a",
        candidate_manifest_sha256s=(
            _sha("other-task-candidate-manifest"),
            manifest.content_sha256,
        ),
    )
    payload = _freeze().model_dump(mode="python", exclude={"content_sha256"})
    payload.update(
        evaluation_plan_ref=_plan_ref(scope.content_sha256),
        evaluation_plan_candidate_manifest_sha256=scope.content_sha256,
        evaluation_plan_candidate_scope=scope,
    )

    freeze = ProposalFreeze.model_validate(payload)

    assert freeze.evaluation_plan_candidate_scope == scope
    assert manifest.content_sha256 in scope.candidate_manifest_sha256s

    nonmember_scope = CandidateManifestScope(
        scope_id="candidate-scope.wrong",
        candidate_manifest_sha256s=(_sha("other-task-candidate-manifest"),),
    )
    payload.update(
        evaluation_plan_ref=_plan_ref(nonmember_scope.content_sha256),
        evaluation_plan_candidate_manifest_sha256=nonmember_scope.content_sha256,
        evaluation_plan_candidate_scope=nonmember_scope,
    )
    with pytest.raises(ValidationError, match="candidate manifest is not a member"):
        ProposalFreeze.model_validate(payload)


def test_structural_freeze_content_identity_matches_current_payload() -> None:
    freeze = _freeze()
    payload = freeze.model_dump(mode="json")

    assert "selected_provider_calibration_task_sha256" not in payload
    assert "provider_calibration_manifest_sha256" not in payload
    assert "provider_calibration_release_authority_event_sha256" not in payload
    current_payload = {key: value for key, value in payload.items() if key != "content_sha256"}
    current_content_sha256 = canonical_content_sha256(current_payload)

    assert freeze.content_sha256 == current_content_sha256
    assert (
        ProposalFreeze.model_validate(
            {
                **current_payload,
                "content_sha256": current_content_sha256,
            }
        )
        == freeze
    )


def test_structural_freeze_can_bind_an_execution_profile() -> None:
    profile_sha256 = _sha("proposal-execution-profile")
    freeze = ProposalFreeze.model_validate(
        {
            **_freeze().model_dump(mode="json", exclude={"content_sha256"}),
            "execution_profile_sha256": profile_sha256,
        }
    )

    assert freeze.schema_version == "aecbench.evaluation-proposal-freeze.v3"
    assert freeze.execution_profile_sha256 == profile_sha256
    assert freeze.model_dump(mode="json")["execution_profile_sha256"] == profile_sha256
    assert freeze.content_sha256 != _freeze().content_sha256


def test_generic_calibration_freeze_binds_one_evaluation_cohort() -> None:
    payload = _freeze().model_dump(mode="python", exclude={"content_sha256"})
    payload.update(
        schema_version="aecbench.evaluation-proposal-freeze.v3",
        split=OptimizationSplit.CALIBRATION,
        selected_structural_item_sha256=None,
        evaluation_cohort=EvaluationCohortBinding(
            cohort_id="cohort.calibration",
            evaluation_generation="generation.calibration",
            cohort_sha256=_sha("evaluation-cohort"),
            release_authority_event_sha256=_sha("cohort-release"),
        ),
    )

    freeze = ProposalFreeze.model_validate(payload)
    encoded = freeze.model_dump(mode="json")

    assert freeze.evaluation_cohort.cohort_id == "cohort.calibration"
    assert "provider_calibration_manifest_sha256" not in encoded
    assert "provider_calibration_release_authority_event_sha256" not in encoded
    assert "provider_calibration_evaluation_seed" not in encoded


def _coordinates() -> tuple[MatchedEvaluationCoordinate, ...]:
    return (
        MatchedEvaluationCoordinate(
            coordinate_id="evaluation-coordinate.1",
            task_id="drainage-01",
            task_revision=_sha("task-revision"),
            split=OptimizationSplit.DEVELOPMENT,
            review_lineage_id=_sha("selected-review-lineage"),
            seed=11,
            repetition=0,
        ),
        MatchedEvaluationCoordinate(
            coordinate_id="evaluation-coordinate.2",
            task_id="drainage-01",
            task_revision=_sha("task-revision"),
            split=OptimizationSplit.DEVELOPMENT,
            review_lineage_id=_sha("selected-review-lineage"),
            seed=22,
            repetition=0,
        ),
    )


def _evidence(
    candidate: ProgramCandidateRef,
    coordinate: MatchedEvaluationCoordinate,
    *,
    complete: bool = True,
    integrity: bool = True,
) -> MatchedCandidateEvidenceRef:
    label = f"{candidate.candidate_id}:{coordinate.coordinate_id}"
    return MatchedCandidateEvidenceRef(
        evidence_id=f"evidence.{label}",
        candidate_id=candidate.candidate_id,
        coordinate_sha256=coordinate.content_sha256,
        kind=CandidateEvidenceKind.TRIAL_RECORD,
        trial_record_sha256=_sha(f"trial:{label}"),
        evaluation_outcome_sha256=_sha(f"outcome:{label}"),
        evidence_complete=complete,
        integrity_passed=integrity,
    )


def test_matched_evidence_distinguishes_trials_from_compile_rejections() -> None:
    coordinate = _coordinates()[0]
    proposal = _proposal("candidate.1", 1)
    base = {
        "evidence_id": "evidence.compile-rejection",
        "candidate_id": proposal.candidate_id,
        "coordinate_sha256": coordinate.content_sha256,
        "kind": CandidateEvidenceKind.COMPILE_REJECTION,
        "trial_record_sha256": None,
        "evaluation_outcome_sha256": _sha("compile-rejection-outcome"),
        "evidence_complete": True,
        "integrity_passed": True,
    }
    rejection = MatchedCandidateEvidenceRef.model_validate(base)
    assert rejection.trial_record_sha256 is None

    with pytest.raises(ValidationError, match="trial-backed evidence requires"):
        MatchedCandidateEvidenceRef.model_validate(
            {
                **base,
                "kind": CandidateEvidenceKind.TRIAL_RECORD,
            }
        )

    with pytest.raises(ValidationError, match="non-trial evidence cannot bind"):
        MatchedCandidateEvidenceRef.model_validate(
            {
                **base,
                "trial_record_sha256": _sha("fabricated-trial"),
            }
        )


def _study() -> ProgramCandidateStudy:
    freeze = _freeze()
    incumbent = _incumbent()
    coordinates = _coordinates()
    candidates = (incumbent, *freeze.realized_candidates)
    evidence = tuple(_evidence(candidate, coordinate) for candidate in candidates for coordinate in coordinates)
    return ProgramCandidateStudy(
        study_id="study.problem-01",
        kernel_sha256=freeze.problem_view.fixed_harness.kernel_sha256,
        fixed_harness_sha256=freeze.fixed_harness_sha256,
        evaluation_plan_ref=freeze.evaluation_plan_ref,
        proposal_freeze=freeze,
        aggregate_budget=freeze.problem_view.fixed_harness.aggregate_budget,
        incumbent_candidate=incumbent,
        coordinates=coordinates,
        evidence_refs=evidence,
    )


def _comparison(
    study: ProgramCandidateStudy,
    challenger: ProgramCandidateRef,
    disposition: OptimizationDisposition,
) -> PairedCandidateComparison:
    incumbent_refs = tuple(
        evidence for evidence in study.evidence_refs if evidence.candidate_id == study.incumbent_candidate.candidate_id
    )
    challenger_refs = tuple(
        evidence for evidence in study.evidence_refs if evidence.candidate_id == challenger.candidate_id
    )
    return PairedCandidateComparison(
        comparison_id=f"comparison.{challenger.candidate_id}",
        study_sha256=study.content_sha256,
        incumbent_candidate=study.incumbent_candidate,
        challenger_candidate=challenger,
        incumbent_evidence_refs=incumbent_refs,
        challenger_evidence_refs=challenger_refs,
        coverage_complete=True,
        integrity_passed=True,
        utility_delta=0.1 if disposition is OptimizationDisposition.ACCEPT else -0.1,
        disposition=disposition,
        selected_candidate_id=(
            challenger.candidate_id
            if disposition is OptimizationDisposition.ACCEPT
            else study.incumbent_candidate.candidate_id
            if disposition is OptimizationDisposition.REJECT
            else None
        ),
    )


def test_problem_view_is_content_addressed_canonical_and_path_free() -> None:
    payload = _view_payload()
    payload["public_sources"] = [
        {
            "source_id": "source.z",
            "opaque_handle": "public-source:z",
            "media_type": "text/plain",
            "byte_size": 2,
            "source_sha256": _sha("z"),
        },
        {
            "source_id": "source.a",
            "opaque_handle": "public-source:a",
            "media_type": "text/plain",
            "byte_size": 1,
            "source_sha256": _sha("a"),
        },
    ]
    payload["fixed_harness"] = {
        **payload["fixed_harness"],  # type: ignore[dict-item]
        "capability_ids": ["tool.write", "context.public", "tool.read"],
    }
    view = DecompositionProblemView.model_validate(payload)

    assert [source.source_id for source in view.public_sources] == ["source.a", "source.z"]
    assert view.fixed_harness.capability_ids == (
        "context.public",
        "tool.read",
        "tool.write",
    )
    assert "path" not in PublicSourceRef.model_fields
    assert view.content_sha256 == DecompositionProblemView.model_validate(view.model_dump(mode="json")).content_sha256


@pytest.mark.parametrize(
    "opaque_handle",
    (
        "/tmp/source.pdf",
        "file:/tmp/source.pdf",
        "source/report.pdf",
        r"source\report.pdf",
        "public-source:../report.pdf",
    ),
)
def test_public_source_handle_is_opaque_not_a_host_or_relative_path(opaque_handle: str) -> None:
    payload = _view_payload()
    sources = payload["public_sources"]
    assert isinstance(sources, list)
    assert isinstance(sources[0], dict)
    sources[0]["opaque_handle"] = opaque_handle

    with pytest.raises(ValidationError, match="opaque and path-free"):
        DecompositionProblemView.model_validate(payload)


def test_problem_and_coordinate_revisions_are_exact_content_identities() -> None:
    payload = _view_payload()
    payload["task_revision"] = "semantic-r1"
    with pytest.raises(ValidationError, match="SHA-256"):
        DecompositionProblemView.model_validate(payload)

    with pytest.raises(ValidationError, match="SHA-256"):
        MatchedEvaluationCoordinate(
            coordinate_id="coordinate.invalid",
            task_id="drainage-01",
            task_revision="semantic-r1",
            split=OptimizationSplit.DEVELOPMENT,
            review_lineage_id="semantic-lineage",
            seed=1,
            repetition=0,
        )


@pytest.mark.parametrize(
    "leaking_key",
    [
        "evaluation_plan",
        "world",
        "world_json",
        "graph",
        "stage",
        "stage_id",
        "stage_count",
        "route",
        "topology",
        "topology_signature",
        "verifier",
        "oracle",
        "reward",
        "trajectory",
        "compiler",
        "compiler_diagnostics",
        "prior_outcome",
        "holdout_motif",
        "critic",
        "critic_spec",
        "authority_policy",
        "eligibility",
        "eligibility_policy",
        "denominator",
        "denominator_policy",
        "evidence_rule",
        "evidence_inclusion_rule",
    ],
)
def test_problem_view_rejects_privileged_fields_recursively(leaking_key: str) -> None:
    payload = copy.deepcopy(_view_payload())
    boundaries = payload["data_gap_boundaries"]
    assert isinstance(boundaries, list)
    assert isinstance(boundaries[0], dict)
    boundaries[0]["metadata"] = {"public": {"nested": {leaking_key: "secret"}}}

    with pytest.raises(ValidationError, match="privileged leakage key"):
        DecompositionProblemView.model_validate(payload)


def test_problem_view_rejects_unknown_non_privileged_fields_too() -> None:
    payload = _view_payload()
    payload["friendly_note"] = "still outside the closed contract"

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        DecompositionProblemView.model_validate(payload)


def test_leakage_audit_represents_pass_and_preconstruction_failure() -> None:
    view = _view()
    passed = _audit(view)
    assert passed.passed is True
    assert passed.problem_view_sha256 == view.content_sha256

    failed = DecompositionLeakageAudit(
        audit_id="audit.rejected",
        audited_input_sha256=_sha("leaked-builder-input"),
        audit_policy_sha256=_sha("leakage-policy"),
        passed=False,
        finding_codes=("public_prompt_names_gold_stage",),
        problem_view_sha256=None,
    )
    assert failed.passed is False

    with pytest.raises(ValidationError, match="passed leakage audit"):
        DecompositionLeakageAudit.model_validate(
            {
                **failed.model_dump(mode="json", exclude={"content_sha256"}),
                "passed": True,
            }
        )


def test_candidate_manifest_canonicalizes_coordinates_and_binds_exact_count() -> None:
    view = _view()
    first = CandidateGenerationCoordinate(
        coordinate_id="coordinate.b",
        candidate_id="candidate.b",
        seed=2,
    )
    second = CandidateGenerationCoordinate(
        coordinate_id="coordinate.a",
        candidate_id="candidate.a",
        seed=1,
    )
    manifest = CandidateGenerationManifest(
        manifest_id="manifest",
        problem_view_sha256=view.content_sha256,
        proposal_policy_sha256=_sha("policy"),
        policy_checkpoint_sha256=_sha("checkpoint"),
        selection_policy_sha256=_sha("selection-policy"),
        expected_candidate_count=2,
        coordinates=(first, second),
        stopping_policy_sha256=_sha("stop"),
    )
    assert [coordinate.coordinate_id for coordinate in manifest.coordinates] == [
        "coordinate.a",
        "coordinate.b",
    ]

    with pytest.raises(ValidationError, match="candidate count"):
        CandidateGenerationManifest.model_validate(
            {
                **manifest.model_dump(mode="json", exclude={"content_sha256"}),
                "expected_candidate_count": 3,
            }
        )

    with pytest.raises(ValidationError, match="SHA-256"):
        CandidateGenerationManifest.model_validate(
            {
                **manifest.model_dump(mode="json", exclude={"content_sha256"}),
                "selection_policy_sha256": "not-a-digest",
            }
        )


def test_proposal_freeze_requires_performance_operator_and_exact_realized_set() -> None:
    freeze = _freeze()
    assert freeze.operator_authority.role is OperatorRole.PERFORMANCE_OPTIMIZATION
    assert freeze.proposal_set_closed is True
    assert freeze.late_candidates_permitted is False

    with pytest.raises(ValidationError, match="performance_optimization"):
        ProposalFreeze.model_validate(
            {
                **freeze.model_dump(mode="json", exclude={"content_sha256"}),
                "operator_authority": operator_authority_for(
                    "repairer",
                    OperatorRole.DIAGNOSTIC_REPAIR,
                ).model_dump(mode="json"),
            }
        )

    with pytest.raises(ValidationError, match="exact realized candidate set"):
        ProposalFreeze.model_validate(
            {
                **freeze.model_dump(mode="json", exclude={"content_sha256"}),
                "realized_candidates": [
                    freeze.realized_candidates[0].model_dump(mode="json"),
                ],
            }
        )


def test_proposal_freeze_rejects_plan_manifest_or_policy_drift() -> None:
    freeze = _freeze()
    base = freeze.model_dump(mode="json", exclude={"content_sha256"})

    with pytest.raises(ValidationError, match="candidate manifest"):
        ProposalFreeze.model_validate(
            {
                **base,
                "evaluation_plan_candidate_manifest_sha256": _sha("different-manifest"),
            }
        )

    with pytest.raises(ValidationError, match="proposal policy"):
        ProposalFreeze.model_validate(
            {
                **base,
                "proposal_policy_sha256": _sha("different-policy"),
            }
        )

    with pytest.raises(ValidationError, match="SHA-256"):
        ProposalFreeze.model_validate(
            {
                **base,
                "structural_split_sha256": "not-a-digest",
            }
        )

    with pytest.raises(ValidationError, match="SHA-256"):
        ProposalFreeze.model_validate(
            {
                **base,
                "selected_review_lineage_id": "semantic-label-is-not-lineage",
            }
        )


def test_proposal_freeze_rejects_problem_view_and_checkpoint_drift() -> None:
    freeze = _freeze()
    base = freeze.model_dump(mode="json", exclude={"content_sha256"})
    mismatched_audit = DecompositionLeakageAudit(
        audit_id="audit.other-problem-view",
        audited_input_sha256=_sha("other-public-builder-input"),
        audit_policy_sha256=_sha("leakage-policy"),
        passed=True,
        finding_codes=(),
        problem_view_sha256=_sha("other-problem-view"),
    )

    with pytest.raises(ValidationError, match="leakage audit does not bind"):
        ProposalFreeze.model_validate(
            {
                **base,
                "leakage_audit": mismatched_audit.model_dump(mode="json"),
            }
        )

    other_manifest = CandidateGenerationManifest.model_validate(
        {
            **freeze.candidate_manifest.model_dump(
                mode="json",
                exclude={"content_sha256"},
            ),
            "problem_view_sha256": _sha("other-problem-view"),
        }
    )
    with pytest.raises(ValidationError, match="candidate manifest does not bind"):
        ProposalFreeze.model_validate(
            {
                **base,
                "candidate_manifest": other_manifest.model_dump(mode="json"),
            }
        )

    with pytest.raises(ValidationError, match="policy checkpoint"):
        ProposalFreeze.model_validate(
            {
                **base,
                "policy_checkpoint_sha256": _sha("different-checkpoint"),
            }
        )


def test_proposal_freeze_rejects_obsolete_provider_calibration_fields() -> None:
    freeze = _freeze()
    structural_payload = freeze.model_dump(mode="json", exclude={"content_sha256"})

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ProposalFreeze.model_validate(
            {
                **structural_payload,
                "provider_calibration_manifest_sha256": _sha("provider-manifest"),
            }
        )


def test_study_requires_exact_kernel_h0_plan_budget_split_and_cross_product() -> None:
    study = _study()
    assert len(study.evidence_refs) == 6

    mutations = (
        ("kernel_sha256", _sha("other-kernel"), "kernel"),
        ("fixed_harness_sha256", _sha("other-h0"), "fixed H0"),
        ("aggregate_budget", HarnessBudget().model_dump(mode="json"), "aggregate budget"),
        (
            "evaluation_plan_ref",
            _plan_ref(_sha("other-candidate-manifest")).model_dump(mode="json"),
            "evaluation plan",
        ),
    )
    for field, value, message in mutations:
        with pytest.raises(ValidationError, match=message):
            ProgramCandidateStudy.model_validate(
                {
                    **study.model_dump(mode="json", exclude={"content_sha256"}),
                    field: value,
                }
            )

    with pytest.raises(ValidationError, match="exact candidate-coordinate coverage"):
        ProgramCandidateStudy.model_validate(
            {
                **study.model_dump(mode="json", exclude={"content_sha256"}),
                "evidence_refs": [evidence.model_dump(mode="json") for evidence in study.evidence_refs[:-1]],
            }
        )


@pytest.mark.parametrize(
    ("coordinate_field", "value", "message"),
    (
        ("split", OptimizationSplit.TRAINING, "split"),
        ("task_id", "other-task", "task"),
        ("review_lineage_id", _sha("other-lineage"), "review lineage"),
    ),
)
def test_study_rejects_coordinate_drift(
    coordinate_field: str,
    value: object,
    message: str,
) -> None:
    study = _study()
    coordinate = study.coordinates[0]
    changed_coordinate = MatchedEvaluationCoordinate.model_validate(
        {
            **coordinate.model_dump(mode="json", exclude={"content_sha256"}),
            coordinate_field: value,
        }
    )

    with pytest.raises(ValidationError, match=message):
        ProgramCandidateStudy.model_validate(
            {
                **study.model_dump(mode="json", exclude={"content_sha256"}),
                "coordinates": [
                    changed_coordinate.model_dump(mode="json"),
                    study.coordinates[1].model_dump(mode="json"),
                ],
            }
        )


def test_study_rejects_coordinate_id_aliases_for_the_same_semantic_run() -> None:
    study = _study()
    original = study.coordinates[0]
    alias = MatchedEvaluationCoordinate.model_validate(
        {
            **original.model_dump(mode="json", exclude={"content_sha256"}),
            "coordinate_id": "evaluation-coordinate.alias",
        }
    )

    with pytest.raises(ValidationError, match="semantic identities must be unique"):
        ProgramCandidateStudy.model_validate(
            {
                **study.model_dump(mode="json", exclude={"content_sha256"}),
                "coordinates": [
                    original.model_dump(mode="json"),
                    alias.model_dump(mode="json"),
                    study.coordinates[1].model_dump(mode="json"),
                ],
            }
        )


def test_comparison_accept_reject_abstain_and_error_semantics_are_closed() -> None:
    study = _study()
    challenger = study.proposal_freeze.realized_candidates[0]
    accepted = _comparison(study, challenger, OptimizationDisposition.ACCEPT)
    assert accepted.selected_candidate_id == challenger.candidate_id

    with pytest.raises(ValidationError, match="coverage flag does not match"):
        PairedCandidateComparison.model_validate(
            {
                **accepted.model_dump(mode="json", exclude={"content_sha256"}),
                "coverage_complete": False,
            }
        )

    with pytest.raises(ValidationError, match="experiment_error"):
        PairedCandidateComparison.model_validate(
            {
                **accepted.model_dump(mode="json", exclude={"content_sha256"}),
                "disposition": OptimizationDisposition.EXPERIMENT_ERROR,
            }
        )

    failed_challenger_evidence = tuple(
        MatchedCandidateEvidenceRef.model_validate(
            {
                **evidence.model_dump(mode="json", exclude={"content_sha256"}),
                "evidence_complete": False,
            }
        )
        for evidence in accepted.challenger_evidence_refs
    )
    errored = PairedCandidateComparison(
        comparison_id="comparison.error",
        study_sha256=study.content_sha256,
        incumbent_candidate=study.incumbent_candidate,
        challenger_candidate=challenger,
        incumbent_evidence_refs=accepted.incumbent_evidence_refs,
        challenger_evidence_refs=failed_challenger_evidence,
        coverage_complete=False,
        integrity_passed=True,
        utility_delta=None,
        disposition=OptimizationDisposition.EXPERIMENT_ERROR,
        selected_candidate_id=None,
    )
    assert errored.disposition is OptimizationDisposition.EXPERIMENT_ERROR


def test_comparison_rejects_evidence_identity_and_integrity_drift() -> None:
    study = _study()
    challenger = study.proposal_freeze.realized_candidates[0]
    accepted = _comparison(study, challenger, OptimizationDisposition.ACCEPT)
    wrong_incumbent_evidence = MatchedCandidateEvidenceRef.model_validate(
        {
            **accepted.incumbent_evidence_refs[0].model_dump(
                mode="json",
                exclude={"content_sha256"},
            ),
            "candidate_id": challenger.candidate_id,
        }
    )

    with pytest.raises(ValidationError, match="incumbent evidence does not bind"):
        PairedCandidateComparison.model_validate(
            {
                **accepted.model_dump(mode="json", exclude={"content_sha256"}),
                "incumbent_evidence_refs": [
                    wrong_incumbent_evidence.model_dump(mode="json"),
                    accepted.incumbent_evidence_refs[1].model_dump(mode="json"),
                ],
            }
        )

    failed_integrity_evidence = MatchedCandidateEvidenceRef.model_validate(
        {
            **accepted.challenger_evidence_refs[0].model_dump(
                mode="json",
                exclude={"content_sha256"},
            ),
            "integrity_passed": False,
        }
    )
    with pytest.raises(ValidationError, match="integrity flag does not match"):
        PairedCandidateComparison.model_validate(
            {
                **accepted.model_dump(mode="json", exclude={"content_sha256"}),
                "challenger_evidence_refs": [
                    failed_integrity_evidence.model_dump(mode="json"),
                    accepted.challenger_evidence_refs[1].model_dump(mode="json"),
                ],
            }
        )


def test_optimization_cycle_schedules_and_completes_every_frozen_candidate() -> None:
    study = _study()
    comparisons = tuple(
        _comparison(study, challenger, OptimizationDisposition.REJECT)
        for challenger in study.proposal_freeze.realized_candidates
    )
    candidate_ids = tuple(candidate.candidate_id for candidate in study.proposal_freeze.realized_candidates)
    cycle = DecompositionOptimizationCycle(
        cycle_id="cycle.problem-01",
        study=study,
        scheduled_candidate_ids=candidate_ids,
        completed_candidate_ids=candidate_ids,
        comparisons=comparisons,
        cycle_complete=True,
        disposition=OptimizationDisposition.REJECT,
        selected_candidate_id=study.incumbent_candidate.candidate_id,
    )
    assert cycle.selected_candidate_id == "candidate.incumbent"
    assert "repair" not in " ".join(type(cycle).model_fields)

    with pytest.raises(ValidationError, match="complete frozen candidate schedule"):
        DecompositionOptimizationCycle.model_validate(
            {
                **cycle.model_dump(mode="json", exclude={"content_sha256"}),
                "completed_candidate_ids": [candidate_ids[0]],
            }
        )


@pytest.mark.parametrize(
    "repair_field",
    [
        "diagnosis",
        "repair_trigger",
        "patch",
        "parent_candidate",
        "child_candidate",
        "no_repair_required",
        "repair_iteration",
    ],
)
def test_optimization_cycle_rejects_repair_semantics(repair_field: str) -> None:
    study = _study()
    candidate_ids = tuple(candidate.candidate_id for candidate in study.proposal_freeze.realized_candidates)
    comparisons = tuple(
        _comparison(study, challenger, OptimizationDisposition.REJECT)
        for challenger in study.proposal_freeze.realized_candidates
    )
    payload = {
        "cycle_id": "cycle.problem-01",
        "study": study.model_dump(mode="json"),
        "scheduled_candidate_ids": candidate_ids,
        "completed_candidate_ids": candidate_ids,
        "comparisons": [comparison.model_dump(mode="json") for comparison in comparisons],
        "cycle_complete": True,
        "disposition": OptimizationDisposition.REJECT,
        "selected_candidate_id": study.incumbent_candidate.candidate_id,
        repair_field: "forbidden",
    }
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        DecompositionOptimizationCycle.model_validate(payload)
