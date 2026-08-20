# ABOUTME: Tests governed freezing of exact proposal sets before any candidate evaluation begins.
# ABOUTME: Proves full host evidence stays ledger-confined while freeze authority remains replayable.

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import pytest

from aec_bench.contracts.artifacts import ArtifactRef
from aec_bench.contracts.authority import (
    AuthorityAction,
    AuthorityDecision,
    AuthorityPrincipal,
    AuthorityPrincipalKind,
    OperatorRole,
    TaintLabel,
    operator_authority_for,
)
from aec_bench.contracts.evaluation_plane import (
    AcceptanceManifestCommitment,
    AcceptancePolicy,
    CandidateManifestScope,
    Critic,
    CriticFeedbackVisibility,
    CriticRole,
    DenominatorPolicy,
    EligibilityPolicy,
    EvaluationAssignment,
    EvaluationBudget,
    EvaluationBudgetPartition,
    EvaluationRegime,
    EvidencePolicy,
    MonitoringPolicy,
    RepositoryCriticSource,
    StoppingPolicy,
    candidate_manifest_scope_commitment,
)
from aec_bench.contracts.harness_instance import CompiledHarnessInstance
from aec_bench.contracts.harness_kernel import KernelRef, canonical_json_sha256
from aec_bench.contracts.output_completion import OutputCompletionContract
from aec_bench.contracts.program_proposal.candidate import (
    CandidateGenerationCoordinate,
    CandidateGenerationManifest,
    ProgramCandidateRef,
)
from aec_bench.contracts.program_proposal.freeze import ProposalFreeze
from aec_bench.contracts.program_proposal.problem import (
    DecompositionLeakageAudit,
    DecompositionProblemView,
    PublicAuthorityBoundary,
    PublicDataGapBoundary,
)
from aec_bench.contracts.program_proposal.study import MatchedEvaluationCoordinate
from aec_bench.contracts.program_proposal.types import OptimizationSplit, ProgramCandidateKind
from aec_bench.contracts.proposal_execution_profile import (
    ProposalExecutionProfile,
)
from aec_bench.contracts.task_definition import Visibility
from aec_bench.contracts.task_review_snapshot import TaskReviewSnapshot as TaskReviewSnapshotRef
from aec_bench.contracts.task_snapshot import ArtifactTaskSnapshotRef as TaskSnapshotRef
from aec_bench.evaluation.regime import expected_evaluation_regime_ref
from aec_bench.experimentation.governance.authority_ledger import (
    AuthorityLedger,
    AuthorityLedgerIntegrityError,
)
from aec_bench.experimentation.proposals.decomposition_optimization import (
    DecompositionExecutionSchedule,
    FrozenSelectionRule,
    build_decomposition_execution_schedule,
)
from aec_bench.experimentation.proposals.freezing import (
    GovernedProposalFreezeError,
    GovernedProposalFreezeResult,
    ProposalArtifact,
    ProposalFreezeBasis,
    assert_proposal_freeze_authority,
    issue_governed_proposal_freeze,
)
from aec_bench.experimentation.proposals.pre_execution_protocol import (
    PreExecutionProtocolSpec,
    load_pre_execution_protocol_evidence,
    record_pre_execution_protocol,
)
from aec_bench.experimentation.proposals.problem_view import (
    PublicSourceBinding,
    build_decomposition_problem_view,
)
from aec_bench.experimentation.proposals.program_compilation import (
    proposal_execution_profile,
)
from aec_bench.experimentation.proposals.structural_corpus import (
    StructuralCorpusItem,
    StructuralSplit,
    StructuralSplitManifest,
    build_structural_split_manifest,
    topology_shape_ref,
)
from aec_bench.harness.compilation.task_snapshot import build_task_snapshot
from aec_bench.harness.kernel_catalogue import default_kernel_registry
from aec_bench.tasks.loader import load_task_definition
from tests.support.adaptive_harness import build_adaptive_bundle, write_adaptive_task

_OUTPUT_CONTRACT = {
    "schema_version": "aecbench.output-completion-contract.v1",
    "output_path": "/workspace/output.md",
    "format": "markdown_final_fenced_json",
    "required_top_level_keys": ["decision", "basis"],
    "require_single_final_json_block": True,
}


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _execution_profile(fixture: _Fixture) -> ProposalExecutionProfile:
    registry = default_kernel_registry()
    return proposal_execution_profile(
        registry=registry,
        fixed_harness=fixture.fixed_harness,
        provider_broker_required=False,
    )


@dataclass(frozen=True)
class _Fixture:
    ledger: AuthorityLedger
    evaluation_regime: EvaluationRegime
    evaluation_assignment: EvaluationAssignment
    structural_split: StructuralSplitManifest
    task_snapshot: TaskSnapshotRef
    leakage_audit: DecompositionLeakageAudit
    problem_view: DecompositionProblemView
    candidate_manifest: CandidateGenerationManifest
    fixed_harness: CompiledHarnessInstance
    proposal_policy: bytes
    policy_checkpoint: bytes
    proposal_artifacts: tuple[ProposalArtifact, ...]
    host_policy: AuthorityPrincipal
    host_runtime: AuthorityPrincipal


def test_governed_freeze_persists_complete_basis_and_immediately_replays_it(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)

    result = _issue(fixture)

    assert result.freeze.fixed_harness_ref == fixture.fixed_harness.ref
    assert result.freeze.evaluation_regime_ref == fixture.evaluation_assignment.regime
    selected_item = fixture.structural_split.dev.items[0]
    assert result.freeze.selected_structural_item_sha256 == canonical_json_sha256(selected_item.model_dump(mode="json"))
    assert result.freeze.selected_review_lineage_id == selected_item.review_lineage_id
    assert result.freeze.execution_profile_sha256 is None
    assert result.basis.execution_profile is None
    basis_payload = result.basis.model_dump(mode="json")
    assert "execution_profile" not in basis_payload
    basis_content = {key: value for key, value in basis_payload.items() if key != "content_sha256"}
    basis_sha256 = canonical_json_sha256(basis_content)
    assert result.basis.content_sha256 == basis_sha256
    assert (
        ProposalFreezeBasis.model_validate(
            {
                **basis_content,
                "content_sha256": basis_sha256,
            }
        )
        == result.basis
    )
    encoded_result = json.dumps(result.model_dump(mode="json"), sort_keys=True)
    assert "execution_profile_sha256" not in encoded_result
    assert result.authority_event.action is AuthorityAction.PROPOSAL_FREEZE
    assert result.authority_event.decision is AuthorityDecision.GRANTED
    assert result.authority_event.subject_id == result.freeze.freeze_id
    assert result.authority_event.subject_sha256 == result.freeze.content_sha256
    assert result.authority_event.basis == result.basis.references
    assert result.replay_observation.replayed is True
    assert result.replay_observation.closure_complete is True
    assert result.replay_observation.observed_basis_closure_sha256 == (result.replay_requirement.basis_closure_sha256)

    stored = assert_proposal_freeze_authority(
        ledger=fixture.ledger,
        result=result,
    )
    assert stored.event == result.authority_event
    assert {reference.artifact_id for reference in result.basis.proposal_artifacts} == {
        f"proposal-freeze.{result.freeze.freeze_id}.proposal-artifact.{artifact.reference.candidate_id}"
        for artifact in fixture.proposal_artifacts
    }

    for reference in result.basis.proposal_artifacts:
        proposal_origin = fixture.ledger.resolve_basis(reference).origin
        assert TaintLabel.CANDIDATE_AUTHORED in proposal_origin.taint_labels
        assert TaintLabel.MODEL_REPORTED in proposal_origin.taint_labels
        assert TaintLabel.HUMAN_AUTHORITY not in proposal_origin.taint_labels
        assert TaintLabel.CRITIC_AUTHORITY not in proposal_origin.taint_labels

    freeze_origin = fixture.ledger.resolve_basis(result.basis.freeze).origin
    assert TaintLabel.CANDIDATE_AUTHORED in freeze_origin.taint_labels
    assert TaintLabel.MODEL_REPORTED in freeze_origin.taint_labels
    expected_parent_origins = {
        fixture.ledger.resolve_basis(reference).origin.content_sha256
        for reference in result.basis.references
        if reference != result.basis.freeze
    }
    assert set(freeze_origin.parent_origin_sha256s) == expected_parent_origins


def test_governed_freeze_binds_exact_execution_profile_as_replayable_basis(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    profile = _execution_profile(fixture)

    result = _issue(fixture, execution_profile=profile)

    assert result.freeze.execution_profile_sha256 == profile.content_sha256
    assert result.basis.execution_profile is not None
    assert result.basis.execution_profile in result.authority_event.basis
    assert "execution_profile_change" in result.authority_event.revalidation_triggers
    stored_profile = ProposalExecutionProfile.model_validate_json(
        fixture.ledger.resolve_basis(result.basis.execution_profile).content_path.read_bytes()
    )
    assert stored_profile == profile
    assert_proposal_freeze_authority(ledger=fixture.ledger, result=result)


def test_governed_freeze_observes_a_multitask_candidate_scope(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    scope = CandidateManifestScope(
        scope_id="candidate-scope.phase91a",
        candidate_manifest_sha256s=(
            fixture.candidate_manifest.content_sha256,
            _sha("candidate-manifest.other-task"),
        ),
    )
    assignment = _mutate_assignment(
        fixture.evaluation_assignment,
        candidate_manifest_commitment=candidate_manifest_scope_commitment(scope),
    )

    result = _issue(
        replace(fixture, evaluation_assignment=assignment),
        evaluation_assignment_candidate_scope=scope,
    )

    assert result.freeze.evaluation_assignment_candidate_scope == scope
    assert result.basis.evaluation_assignment_candidate_scope is not None
    stored_scope = CandidateManifestScope.model_validate_json(
        fixture.ledger.resolve_basis(
            result.basis.evaluation_assignment_candidate_scope,
        ).content_path.read_bytes()
    )
    assert stored_scope == scope
    assert result.basis.evaluation_assignment_candidate_scope in result.authority_event.basis
    assert_proposal_freeze_authority(ledger=fixture.ledger, result=result)


def test_public_freeze_result_does_not_expose_acceptance_or_critic_configuration(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)

    result = _issue(fixture)
    public_result = json.dumps(result.model_dump(mode="json"), sort_keys=True)

    assert "hidden-1" not in public_result
    assert "acceptance_critic" not in public_result
    assert "development_critic" not in public_result
    assert result.freeze.evaluation_regime_ref.regime_id in public_result


def _pre_execution_spec() -> PreExecutionProtocolSpec:
    return PreExecutionProtocolSpec(
        protocol_id="proposal-machinery-readiness",
        conclusion="pre_execution_machinery_only",
        proposal_generation_mode="provider_free_optimizer_artifacts",
        proposal_origin_policy="optimizer_only",
        provider_call_policy="zero",
        deferred_status="awaiting_authorized_execution_batch",
        limitations=(
            "candidate execution has not started",
            "this protocol does not establish candidate quality",
        ),
    )


def test_phase_neutral_pre_execution_protocol_persists_and_replays_exact_authority(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "pre-execution"
    fixture = _provider_free_fixture(run_root)
    freeze_result = _issue(fixture)
    schedule = _schedule(fixture, freeze_result)
    spec = _pre_execution_spec()

    result = record_pre_execution_protocol(
        spec=spec,
        ledger=fixture.ledger,
        structural_split=fixture.structural_split,
        proposal_freeze_result=freeze_result,
        execution_schedule=schedule,
        output_root=run_root,
    )
    evidence = load_pre_execution_protocol_evidence(result.path)

    assert evidence.report == result.report
    assert evidence.report.spec == spec
    assert evidence.report.schema_version == "aecbench.pre-execution-protocol-report.v1"
    assert evidence.report.scheduled_candidate_count == 3
    assert evidence.report.scheduled_coordinate_count == 2
    assert evidence.report.scheduled_assignment_count == 6
    assert evidence.report.provider_calls == 0
    assert evidence.report.provider_cost_usd == 0.0
    assert evidence.report.promotion_permitted is False
    assert evidence.structural_split == fixture.structural_split
    assert result.path.parent.name == result.report.content_sha256
    assert result.path.name == "pre-execution-protocol-report.json"


def test_phase_neutral_pre_execution_protocol_rejects_model_authored_proposals(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "pre-execution"
    fixture = _fixture(run_root)
    freeze_result = _issue(fixture)

    with pytest.raises(ValueError, match="optimizer-authored"):
        record_pre_execution_protocol(
            spec=PreExecutionProtocolSpec(
                protocol_id="proposal-machinery-readiness",
                conclusion="pre_execution_machinery_only",
                proposal_generation_mode="provider_free_optimizer_artifacts",
                proposal_origin_policy="optimizer_only",
                provider_call_policy="zero",
                deferred_status="awaiting_authorized_execution_batch",
                limitations=("candidate execution has not started",),
            ),
            ledger=fixture.ledger,
            structural_split=fixture.structural_split,
            proposal_freeze_result=freeze_result,
            execution_schedule=_schedule(fixture, freeze_result),
            output_root=run_root,
        )


def test_pre_execution_protocol_report_does_not_publish_hidden_critic_configuration(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "pre-execution"
    fixture = _provider_free_fixture(run_root)
    freeze_result = _issue(fixture)

    result = record_pre_execution_protocol(
        spec=_pre_execution_spec(),
        ledger=fixture.ledger,
        structural_split=fixture.structural_split,
        proposal_freeze_result=freeze_result,
        execution_schedule=_schedule(fixture, freeze_result),
        output_root=run_root,
    )
    public_report = result.path.read_text(encoding="utf-8")

    assert "hidden-1" not in public_report
    assert "acceptance_critic" not in public_report
    assert "development_critic" not in public_report


def test_pre_execution_protocol_loader_fails_closed_when_authority_basis_disappears(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "pre-execution"
    fixture = _provider_free_fixture(run_root)
    freeze_result = _issue(fixture)
    result = record_pre_execution_protocol(
        spec=_pre_execution_spec(),
        ledger=fixture.ledger,
        structural_split=fixture.structural_split,
        proposal_freeze_result=freeze_result,
        execution_schedule=_schedule(fixture, freeze_result),
        output_root=run_root,
    )
    stored = fixture.ledger.resolve_basis(freeze_result.basis.structural_split)
    stored.content_path.unlink()

    with pytest.raises(ValueError, match="authority replay failed"):
        load_pre_execution_protocol_evidence(result.path)


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        ("plan_ref", "candidate manifest"),
        ("split", "structural split"),
        ("task_manifest", "task manifest"),
        ("kernel", "kernel"),
        ("harness_policy", "harness policy"),
        ("stopping_policy", "evaluation regime reference"),
        ("selection_policy", "evaluation regime reference"),
        ("policy_bytes", "proposal policy"),
        ("checkpoint_bytes", "policy checkpoint"),
        ("proposal_bytes", "proposal artifact"),
    ),
)
def test_freeze_rejects_exact_binding_or_byte_mismatches(
    tmp_path: Path,
    mutation: str,
    message: str,
) -> None:
    fixture = _fixture(tmp_path)
    kwargs: dict[str, Any] = {}
    if mutation == "plan_ref":
        fixture = replace(
            fixture,
            evaluation_assignment=_mutate_assignment(
                fixture.evaluation_assignment,
                candidate_manifest_commitment=_sha("different-candidate-manifest"),
            ),
        )
    elif mutation == "split":
        fixture = replace(
            fixture,
            evaluation_assignment=_mutate_assignment(
                fixture.evaluation_assignment,
                split_manifest_commitment=_sha("different-structural-split"),
            ),
        )
    elif mutation == "task_manifest":
        fixture = replace(
            fixture,
            evaluation_assignment=_mutate_assignment(
                fixture.evaluation_assignment,
                task_manifest_commitment=_sha("different-task-manifest"),
            ),
        )
    elif mutation == "kernel":
        fixture = replace(
            fixture,
            evaluation_assignment=_mutate_assignment(
                fixture.evaluation_assignment,
                kernel_ref=KernelRef(
                    kernel_id=fixture.evaluation_assignment.kernel_ref.kernel_id,
                    version="different-kernel-version",
                ),
            ),
        )
    elif mutation == "harness_policy":
        fixture = replace(
            fixture,
            evaluation_assignment=_mutate_assignment(
                fixture.evaluation_assignment,
                harness_policy_commitment=_sha("different-harness-policy"),
            ),
        )
    elif mutation == "stopping_policy":
        fixture = replace(
            fixture,
            evaluation_regime=_mutate_plan(
                fixture.evaluation_regime,
                stopping_policy=StoppingPolicy(
                    policy_id="stopping.changed",
                    configuration={"max_candidates": 3},
                ),
            ),
        )
    elif mutation == "selection_policy":
        fixture = replace(
            fixture,
            evaluation_regime=_mutate_plan(
                fixture.evaluation_regime,
                acceptance_policy=AcceptancePolicy(
                    policy_id="acceptance.changed",
                    configuration={"minimum_utility_delta": 0.1},
                ),
            ),
        )
    elif mutation == "policy_bytes":
        kwargs["proposal_policy"] = b"different proposal policy\n"
    elif mutation == "checkpoint_bytes":
        kwargs["policy_checkpoint"] = b"different policy checkpoint\n"
    elif mutation == "proposal_bytes":
        changed = replace(
            fixture.proposal_artifacts[0],
            content=b'{"candidate_id":"candidate.1","nodes":["changed"]}\n',
        )
        kwargs["proposal_artifacts"] = (changed, *fixture.proposal_artifacts[1:])

    with pytest.raises(GovernedProposalFreezeError, match=message):
        _issue(fixture, **kwargs)


def test_freeze_recomputes_task_normalized_policy_from_the_actual_compiled_h0(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    view_payload = fixture.problem_view.model_dump(mode="json", exclude={"content_sha256"})
    fixed_harness_payload = dict(view_payload["fixed_harness"])
    fixed_harness_payload.pop("content_sha256")
    forged_policy_sha256 = _sha("forged-but-internally-consistent-harness-policy")
    fixed_harness_payload["harness_policy_sha256"] = forged_policy_sha256
    view_payload["fixed_harness"] = fixed_harness_payload
    forged_view = DecompositionProblemView.model_validate(view_payload)
    audit_payload = fixture.leakage_audit.model_dump(mode="json", exclude={"content_sha256"})
    audit_payload["problem_view_sha256"] = forged_view.content_sha256
    forged_audit = DecompositionLeakageAudit.model_validate(audit_payload)
    manifest_payload = fixture.candidate_manifest.model_dump(mode="json", exclude={"content_sha256"})
    manifest_payload["problem_view_sha256"] = forged_view.content_sha256
    forged_manifest = CandidateGenerationManifest.model_validate(manifest_payload)
    forged_assignment = _mutate_assignment(
        fixture.evaluation_assignment,
        candidate_manifest_commitment=forged_manifest.content_sha256,
        harness_policy_commitment=forged_policy_sha256,
    )
    forged_fixture = replace(
        fixture,
        problem_view=forged_view,
        leakage_audit=forged_audit,
        candidate_manifest=forged_manifest,
        evaluation_assignment=forged_assignment,
    )

    with pytest.raises(GovernedProposalFreezeError, match="actual compiled fixed harness"):
        _issue(forged_fixture)


def test_freeze_rejects_wrong_operator_role_and_late_candidate(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)

    with pytest.raises(GovernedProposalFreezeError, match="performance_optimization"):
        _issue(
            fixture,
            operator_authority=operator_authority_for(
                "operator.repair",
                OperatorRole.DIAGNOSTIC_REPAIR,
            ),
        )

    late_content = b'{"candidate_id":"candidate.late","nodes":["run"]}\n'
    late = ProposalArtifact(
        reference=ProgramCandidateRef(
            candidate_id="candidate.late",
            kind=ProgramCandidateKind.PROPOSAL,
            candidate_artifact_sha256=hashlib.sha256(late_content).hexdigest(),
            generation_coordinate_id="coordinate.late",
        ),
        content=late_content,
        producer=fixture.proposal_artifacts[0].producer,
        producer_process_id="proposal-generator",
        invocation_id="invocation.late",
    )
    with pytest.raises(GovernedProposalFreezeError, match="exact realized candidate set"):
        _issue(
            fixture,
            proposal_artifacts=(*fixture.proposal_artifacts, late),
        )


def test_freeze_rejects_unrelated_or_mismatched_selected_structural_item(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    unrelated_snapshot = _task_snapshot("civil/calculation/unrelated", "public-package:unrelated")
    unrelated = _structural_manifest(
        "civil/calculation/unrelated",
        unrelated_snapshot,
    )
    unrelated_fixture = replace(
        fixture,
        structural_split=unrelated,
        evaluation_assignment=_mutate_assignment(
            fixture.evaluation_assignment,
            split_manifest_commitment=unrelated.content_sha256,
            task_manifest_commitment=unrelated.task_manifest_sha256,
        ),
    )

    with pytest.raises(GovernedProposalFreezeError, match="selected structural split"):
        _issue(unrelated_fixture)

    wrong_snapshot = _task_snapshot(fixture.problem_view.task_id, "different-public-package")
    mismatched = _structural_manifest(
        fixture.problem_view.task_id,
        wrong_snapshot,
    )
    mismatched_fixture = replace(
        fixture,
        structural_split=mismatched,
        evaluation_assignment=_mutate_assignment(
            fixture.evaluation_assignment,
            split_manifest_commitment=mismatched.content_sha256,
            task_manifest_commitment=mismatched.task_manifest_sha256,
        ),
    )

    with pytest.raises(GovernedProposalFreezeError, match="task revision"):
        _issue(mismatched_fixture)


def test_optimizer_proposals_remain_candidate_tainted_without_model_authority(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    optimizer = AuthorityPrincipal(
        principal_id="optimizer.decomposition-search",
        kind=AuthorityPrincipalKind.OPTIMIZER,
    )
    optimized = replace(
        fixture.proposal_artifacts[0],
        producer=optimizer,
        producer_process_id="optimizer.decomposition-search",
    )

    result = _issue(
        fixture,
        proposal_artifacts=(optimized, *fixture.proposal_artifacts[1:]),
    )

    optimized_reference = next(
        reference
        for reference in result.basis.proposal_artifacts
        if reference.artifact_id.endswith(".proposal-artifact.candidate.1")
    )
    origin = fixture.ledger.resolve_basis(optimized_reference).origin
    assert origin.producer == optimizer
    assert set(origin.taint_labels) == {
        TaintLabel.CANDIDATE_AUTHORED,
        TaintLabel.RUNTIME_OBSERVED,
    }
    assert TaintLabel.MODEL_REPORTED not in origin.taint_labels
    assert TaintLabel.CRITIC_AUTHORITY not in origin.taint_labels
    assert TaintLabel.HUMAN_AUTHORITY not in origin.taint_labels


@pytest.mark.parametrize(
    ("field_name", "changed_value"),
    (
        ("freeze_id", "freeze.phase9.mutated"),
        ("selected_structural_item_sha256", _sha("different-structural-item")),
        ("selected_review_lineage_id", _sha("different-review-lineage")),
    ),
)
def test_old_freeze_event_cannot_authorize_mutated_freeze(
    tmp_path: Path,
    field_name: str,
    changed_value: str,
) -> None:
    fixture = _fixture(tmp_path)
    result = _issue(fixture)
    payload = result.freeze.model_dump(mode="json", exclude={"content_sha256"})
    payload[field_name] = changed_value
    mutated = ProposalFreeze.model_validate(payload)

    with pytest.raises(GovernedProposalFreezeError, match="exact proposal freeze"):
        assert_proposal_freeze_authority(
            ledger=fixture.ledger,
            result=result,
            freeze=mutated,
        )


def test_unresolvable_basis_fails_closed_after_issuance(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    result = _issue(fixture)
    missing = fixture.ledger.resolve_basis(result.basis.proposal_policy)
    missing.content_path.unlink()

    with pytest.raises(GovernedProposalFreezeError, match="basis"):
        assert_proposal_freeze_authority(
            ledger=fixture.ledger,
            result=result,
        )

    with pytest.raises(AuthorityLedgerIntegrityError, match="missing"):
        fixture.ledger.resolve_basis(result.basis.proposal_policy)


def test_non_host_policy_cannot_issue_proposal_freeze(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)

    with pytest.raises(GovernedProposalFreezeError, match="host_policy"):
        _issue(
            fixture,
            host_policy=AuthorityPrincipal(
                principal_id="model.proposer",
                kind=AuthorityPrincipalKind.MODEL,
            ),
        )


def test_two_task_freezes_can_reuse_local_ids_with_different_exact_bytes(
    tmp_path: Path,
) -> None:
    first = _fixture(
        tmp_path / "first",
        task_id="civil/calculation/adaptive-alpha",
    )
    second = _fixture(
        tmp_path / "second",
        task_id="civil/calculation/adaptive-beta",
    )
    second = replace(second, ledger=first.ledger)

    first_result = _issue(
        first,
        freeze_id="freeze.phase9.alpha",
        event_id="authority.freeze.phase9.alpha",
        replay_id="replay.freeze.phase9.alpha",
    )
    second_result = _issue(
        second,
        freeze_id="freeze.phase9.beta",
        event_id="authority.freeze.phase9.beta",
        replay_id="replay.freeze.phase9.beta",
    )

    assert first_result.freeze.candidate_manifest.manifest_id == (second_result.freeze.candidate_manifest.manifest_id)
    assert first_result.freeze.realized_candidates[0].candidate_id == (
        second_result.freeze.realized_candidates[0].candidate_id
    )
    assert first_result.freeze.realized_candidates[0].candidate_artifact_sha256 != (
        second_result.freeze.realized_candidates[0].candidate_artifact_sha256
    )
    assert first_result.basis.proposal_artifacts[0].artifact_id != second_result.basis.proposal_artifacts[0].artifact_id
    assert (
        assert_proposal_freeze_authority(
            ledger=first.ledger,
            result=first_result,
        ).event
        == first_result.authority_event
    )
    assert (
        assert_proposal_freeze_authority(
            ledger=first.ledger,
            result=second_result,
        ).event
        == second_result.authority_event
    )


def _provider_free_fixture(tmp_path: Path) -> _Fixture:
    fixture = _fixture(tmp_path)
    optimizer = AuthorityPrincipal(
        principal_id="optimizer.phase9-contract-fixture",
        kind=AuthorityPrincipalKind.OPTIMIZER,
    )
    return replace(
        fixture,
        proposal_artifacts=tuple(
            replace(
                artifact,
                producer=optimizer,
                producer_process_id="aecbench.phase9-contract-fixture",
            )
            for artifact in fixture.proposal_artifacts
        ),
    )


def _schedule(
    fixture: _Fixture,
    result: GovernedProposalFreezeResult,
) -> DecompositionExecutionSchedule:
    incumbent_content = b'{"candidate_id":"candidate.incumbent","nodes":[{"node_id":"run"}]}\n'
    incumbent = ProgramCandidateRef(
        candidate_id="candidate.incumbent",
        kind=ProgramCandidateKind.INCUMBENT,
        candidate_artifact_sha256=hashlib.sha256(incumbent_content).hexdigest(),
    )
    coordinates = tuple(
        MatchedEvaluationCoordinate(
            coordinate_id=f"evaluation.dev.{index}",
            task_id=result.freeze.problem_view.task_id,
            task_revision=result.freeze.problem_view.task_revision,
            split=result.freeze.split,
            review_lineage_id=result.freeze.selected_review_lineage_id,
            seed=seed,
            repetition=index,
        )
        for index, seed in enumerate((301, 302), start=1)
    )
    return build_decomposition_execution_schedule(
        schedule_id="schedule.phase9.dev",
        proposal_freeze=result.freeze,
        incumbent_candidate=incumbent,
        coordinates=coordinates,
        kernel_ref=fixture.fixed_harness.kernel_ref,
        fixed_harness_ref=fixture.fixed_harness.ref,
        evaluation_regime_ref=fixture.evaluation_assignment.regime,
        aggregate_budget=fixture.fixed_harness.budget,
    )


def _issue(
    fixture: _Fixture,
    **overrides: Any,
) -> GovernedProposalFreezeResult:
    arguments: dict[str, Any] = {
        "ledger": fixture.ledger,
        "freeze_id": "freeze.phase9.dev",
        "event_id": "authority.freeze.phase9.dev",
        "replay_id": "replay.freeze.phase9.dev",
        "due_cycle_index": 0,
        "evaluation_regime": fixture.evaluation_regime,
        "evaluation_assignment": fixture.evaluation_assignment,
        "operator_authority": operator_authority_for(
            "operator.performance",
            OperatorRole.PERFORMANCE_OPTIMIZATION,
        ),
        "structural_split": fixture.structural_split,
        "split": OptimizationSplit.DEVELOPMENT,
        "leakage_audit": fixture.leakage_audit,
        "problem_view": fixture.problem_view,
        "candidate_manifest": fixture.candidate_manifest,
        "fixed_harness": fixture.fixed_harness,
        "proposal_policy": fixture.proposal_policy,
        "policy_checkpoint": fixture.policy_checkpoint,
        "proposal_artifacts": fixture.proposal_artifacts,
        "host_policy": fixture.host_policy,
        "host_runtime": fixture.host_runtime,
    }
    arguments.update(overrides)
    return issue_governed_proposal_freeze(**arguments)


def _fixture(
    tmp_path: Path,
    *,
    task_id: str = "civil/calculation/adaptive",
    agent_capability_id: str = "aecbench.adapter.tool-loop",
    include_tool_binding: bool = True,
) -> _Fixture:
    tasks_root = tmp_path / "tasks"
    task_dir = write_adaptive_task(
        tasks_root,
        task_id=task_id,
        output_completion_contract=_OUTPUT_CONTRACT,
    )
    (task_dir / "source").mkdir()
    (task_dir / "source" / "rainfall.txt").write_text(
        "The design rainfall depth is 22 mm over a 30 minute duration.\n",
        encoding="utf-8",
    )
    task = load_task_definition(task_dir, tasks_root)
    fixed_harness = build_adaptive_bundle(
        tasks_root=tasks_root,
        task_id=task_id,
        agent_capability_id=agent_capability_id,
        include_tool_binding=include_tool_binding,
    ).harness
    output_contract = OutputCompletionContract.model_validate(_OUTPUT_CONTRACT)
    view_result = build_decomposition_problem_view(
        task=task,
        tasks_root=tasks_root,
        task_snapshot=build_task_snapshot(task=task, tasks_root=tasks_root),
        output_contract=output_contract,
        harness=fixed_harness,
        public_sources=(
            PublicSourceBinding(
                source_id="rainfall-input",
                relative_path="source/rainfall.txt",
                media_type="text/plain",
            ),
        ),
        public_domain_id="civil-drainage",
        public_task_family_id="rainfall-review",
        data_gap_boundaries=(
            PublicDataGapBoundary(
                boundary_id="survey-gap",
                statement="Do not infer values absent from the supplied documents.",
            ),
        ),
        authority_boundaries=(
            PublicAuthorityBoundary(
                boundary_id="human-signoff",
                statement="Final engineering sign-off remains outside the agent scope.",
            ),
        ),
    )
    public_snapshot = build_task_snapshot(task=task, tasks_root=tasks_root)
    structural_split = _structural_manifest(task_id, public_snapshot)
    proposal_policy = b'{"policy":"two-seeded-proposals","version":"1"}\n'
    policy_checkpoint = b"phase9-zero-shot-checkpoint-v1\n"
    selection_rule = FrozenSelectionRule(
        rule_id="rule.minimum-delta",
        minimum_utility_delta=0.05,
    )
    candidate_manifest = CandidateGenerationManifest(
        manifest_id="candidate-manifest.phase9.dev",
        problem_view_sha256=view_result.problem_view.content_sha256,
        proposal_policy_sha256=hashlib.sha256(proposal_policy).hexdigest(),
        policy_checkpoint_sha256=hashlib.sha256(policy_checkpoint).hexdigest(),
        selection_policy_sha256=selection_rule.content_sha256,
        expected_candidate_count=2,
        coordinates=(
            CandidateGenerationCoordinate(
                coordinate_id="coordinate.1",
                candidate_id="candidate.1",
                seed=101,
            ),
            CandidateGenerationCoordinate(
                coordinate_id="coordinate.2",
                candidate_id="candidate.2",
                seed=202,
            ),
        ),
        stopping_policy_sha256=_sha("two-candidates-then-stop"),
    )
    evaluation_regime, evaluation_assignment = _evaluation_surface(
        kernel_ref=fixed_harness.kernel_ref,
        harness_policy_sha256=view_result.problem_view.fixed_harness.harness_policy_sha256,
        candidate_manifest_sha256=candidate_manifest.content_sha256,
        task_manifest_sha256=structural_split.task_manifest_sha256,
        split_manifest_sha256=structural_split.content_sha256,
    )
    model = AuthorityPrincipal(
        principal_id="model.proposal-generator",
        kind=AuthorityPrincipalKind.MODEL,
    )
    proposal_artifacts = tuple(
        _proposal_artifact(
            candidate_id,
            coordinate_id,
            model,
            context_label=task_id,
        )
        for candidate_id, coordinate_id in (
            ("candidate.1", "coordinate.1"),
            ("candidate.2", "coordinate.2"),
        )
    )
    candidate_root = tmp_path / "candidate"
    candidate_root.mkdir()
    return _Fixture(
        ledger=AuthorityLedger(
            tmp_path / "authority",
            candidate_roots=(candidate_root,),
        ),
        evaluation_regime=evaluation_regime,
        evaluation_assignment=evaluation_assignment,
        structural_split=structural_split,
        task_snapshot=public_snapshot,
        leakage_audit=view_result.audit,
        problem_view=view_result.problem_view,
        candidate_manifest=candidate_manifest,
        fixed_harness=fixed_harness,
        proposal_policy=proposal_policy,
        policy_checkpoint=policy_checkpoint,
        proposal_artifacts=proposal_artifacts,
        host_policy=AuthorityPrincipal(
            principal_id="host.proposal-freeze-policy",
            kind=AuthorityPrincipalKind.HOST_POLICY,
        ),
        host_runtime=AuthorityPrincipal(
            principal_id="host.runtime",
            kind=AuthorityPrincipalKind.HOST_RUNTIME,
        ),
    )


def _proposal_artifact(
    candidate_id: str,
    coordinate_id: str,
    producer: AuthorityPrincipal,
    *,
    context_label: str,
) -> ProposalArtifact:
    content = (
        json.dumps(
            {
                "candidate_id": candidate_id,
                "task_context": context_label,
                "nodes": [{"node_id": "run", "operation_id": "run_batch"}],
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        + b"\n"
    )
    return ProposalArtifact(
        reference=ProgramCandidateRef(
            candidate_id=candidate_id,
            kind=ProgramCandidateKind.PROPOSAL,
            candidate_artifact_sha256=hashlib.sha256(content).hexdigest(),
            generation_coordinate_id=coordinate_id,
        ),
        content=content,
        producer=producer,
        producer_process_id="proposal-generator",
        invocation_id=f"invocation.{coordinate_id}",
    )


def _evaluation_surface(
    *,
    kernel_ref: KernelRef,
    harness_policy_sha256: str,
    candidate_manifest_sha256: str,
    task_manifest_sha256: str,
    split_manifest_sha256: str,
) -> tuple[EvaluationRegime, EvaluationAssignment]:
    commitment = AcceptanceManifestCommitment.create(
        critic_id="critic.acceptance",
        case_manifest={"case_ids": ["hidden-1"], "split": "acceptance"},
        scoring_policy={"threshold": 0.8},
        salt="retirement-only-salt",
    )
    regime = EvaluationRegime(
        regime_id="evaluation-regime.phase9",
        critics=(
            _critic(
                CriticRole.DEVELOPMENT,
                case_label="development-cases",
                principal="principal.dev",
            ),
            _critic(
                CriticRole.ACCEPTANCE,
                case_label="acceptance-cases",
                principal="principal.accept",
                commitment=commitment,
            ),
            _critic(
                CriticRole.RED_TEAM,
                case_label="red-team-cases",
                principal="principal.red",
            ),
        ),
        budget=_budgets(),
        acceptance_policy=AcceptancePolicy(
            policy_id="acceptance.phase9",
            configuration={"minimum_utility_delta": 0.05},
        ),
        eligibility_policy=EligibilityPolicy(
            policy_id="eligibility.phase9",
            configuration={"integrity": "required"},
        ),
        denominator_policy=DenominatorPolicy(
            policy_id="denominator.phase9",
            configuration={"population": "all_planned"},
        ),
        evidence_policy=EvidencePolicy(
            policy_id="evidence.phase9",
            configuration={"authority_owned": True},
        ),
        stopping_policy=StoppingPolicy(
            policy_id="stopping.phase9",
            configuration={"max_candidates": 2},
        ),
        monitoring_policy=MonitoringPolicy(
            policy_id="monitoring.phase9",
            configuration={"enabled": True},
        ),
    )
    regime_ref = expected_evaluation_regime_ref(regime)
    return regime, EvaluationAssignment(
        assignment_id="evaluation-assignment.phase9",
        regime=regime_ref,
        kernel_ref=kernel_ref,
        harness_policy_commitment=harness_policy_sha256,
        candidate_manifest_commitment=candidate_manifest_sha256,
        task_manifest_commitment=task_manifest_sha256,
        split_manifest_commitment=split_manifest_sha256,
        task_verifier_commitment=_sha("task-verifier"),
    )


def _critic(
    role: CriticRole,
    *,
    case_label: str,
    principal: str,
    commitment: AcceptanceManifestCommitment | None = None,
) -> Critic:
    return Critic(
        critic_id=f"critic.{role.value}",
        role=role,
        source=RepositoryCriticSource(source_revision="1" * 40, entrypoint="tests.evaluation:score"),
        configuration=(
            {"runtime_mode": "host_only"}
            if role is CriticRole.ACCEPTANCE
            else {"rubric": _sha(f"rubric:{role.value}"), "cases": _sha(case_label)}
        ),
        feedback_visibility=(
            CriticFeedbackVisibility.VISIBLE if role is CriticRole.DEVELOPMENT else CriticFeedbackVisibility.HOST_ONLY
        ),
        execution_principal_id=principal,
        acceptance_manifest_commitment=commitment,
    )


def _budgets() -> EvaluationBudget:
    partition = EvaluationBudgetPartition(
        case_count=2,
        max_attempts=4,
        max_turns=16,
        max_tokens=50_000,
        max_cost_usd=1.0,
        max_wall_time_seconds=600,
    )
    return EvaluationBudget(
        proposal=partition,
        execution=partition,
        development=partition,
        acceptance=partition,
        red_team=partition,
        monitor=partition,
        audit=partition,
    )


def _mutate_plan(plan: EvaluationRegime, **updates: object) -> EvaluationRegime:
    payload = plan.model_dump(mode="json")
    payload.update(updates)
    return EvaluationRegime.model_validate(payload)


def _mutate_assignment(assignment: EvaluationAssignment, **updates: object) -> EvaluationAssignment:
    payload = assignment.model_dump(mode="json")
    payload.update(updates)
    return EvaluationAssignment.model_validate(payload)


def _structural_manifest(
    dev_task_id: str,
    dev_public_snapshot: TaskSnapshotRef,
) -> StructuralSplitManifest:
    return build_structural_split_manifest(
        manifest_id="structural-split.phase9",
        train=StructuralSplit(
            split="train",
            items=(
                _structural_item(
                    "train-task",
                    "drainage",
                    "train-review",
                    node_count=2,
                    visibility=Visibility.PUBLIC,
                ),
            ),
        ),
        dev=StructuralSplit(
            split="dev",
            items=(
                _structural_item(
                    dev_task_id,
                    "drainage",
                    "dev-review",
                    node_count=3,
                    visibility=Visibility.PUBLIC,
                    public_snapshot=dev_public_snapshot,
                ),
            ),
        ),
        holdout=StructuralSplit(
            split="holdout",
            items=(
                _structural_item(
                    "holdout-task",
                    "drainage",
                    "holdout-review",
                    node_count=4,
                    visibility=Visibility.HOLDOUT,
                    diamond=True,
                ),
            ),
        ),
    )


def _structural_item(
    task_id: str,
    family: str,
    lineage: str,
    *,
    node_count: int,
    visibility: Visibility,
    diamond: bool = False,
    public_snapshot: TaskSnapshotRef | None = None,
) -> StructuralCorpusItem:
    nodes = tuple(f"n{index}" for index in range(node_count))
    if diamond:
        edges = (
            (nodes[0], nodes[1]),
            (nodes[0], nodes[2]),
            (nodes[1], nodes[3]),
            (nodes[2], nodes[3]),
        )
    else:
        edges = tuple((nodes[index], nodes[index + 1]) for index in range(node_count - 1))
    selected_public_snapshot = public_snapshot or _task_snapshot(task_id, f"public-package:{task_id}")
    return StructuralCorpusItem(
        task_id=task_id,
        semantic_family=family,
        review_lineage_id=lineage,
        visibility=visibility,
        public_snapshot=selected_public_snapshot,
        snapshot=_task_snapshot(task_id, f"sealed-package:{task_id}"),
        review=TaskReviewSnapshotRef(
            task_id=task_id,
            profile_id=lineage,
            visibility=visibility,
        ),
        topology=topology_shape_ref(nodes=nodes, edges=edges),
    )


def _task_snapshot(task_id: str, label: str) -> TaskSnapshotRef:
    digest = _sha(label)
    return TaskSnapshotRef(
        task_id=task_id,
        artifact=ArtifactRef(
            artifact_id=f"artifacts/sha256/{digest}",
            sha256=digest,
            size_bytes=len(label.encode("utf-8")),
            media_type="application/vnd.aec-bench.task-snapshot+tar+zstd",
        ),
    )
