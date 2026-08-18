# ABOUTME: Validates proposal-freeze principals and exact frozen bindings.
# ABOUTME: Keeps task, harness, policy, and candidate checks ordered and fail closed.

from __future__ import annotations

import hashlib

from aec_bench.contracts.authority import (
    AuthorityPrincipal,
    AuthorityPrincipalKind,
    OperatorAuthority,
    OperatorRole,
)
from aec_bench.contracts.evaluation_plane import (
    CandidateManifestScope,
    EvaluationAssignment,
    EvaluationRegime,
    candidate_manifest_scope_commitment,
)
from aec_bench.contracts.harness_instance import (
    CompiledHarnessInstance,
    TaskSourceBindingConfig,
)
from aec_bench.contracts.harness_kernel import canonical_json_sha256
from aec_bench.contracts.program_proposal.candidate import CandidateGenerationManifest
from aec_bench.contracts.program_proposal.problem import DecompositionLeakageAudit, DecompositionProblemView
from aec_bench.contracts.program_proposal.types import OptimizationSplit, ProgramCandidateKind
from aec_bench.evaluation.regime import validate_evaluation_regime_ref
from aec_bench.experimentation.proposals.freezing.contracts import (
    GovernedProposalFreezeError,
    IncumbentArtifact,
    ProposalArtifact,
    SelectedTaskBinding,
)
from aec_bench.experimentation.proposals.problem_view import (
    fixed_harness_policy_sha256,
)
from aec_bench.experimentation.proposals.structural_corpus import (
    StructuralSplitManifest,
)


def validate_principals(
    *,
    operator: OperatorAuthority,
    host_policy: AuthorityPrincipal,
    host_runtime: AuthorityPrincipal,
) -> None:
    """Validate the exact policy and observation authority roles."""

    if operator.role is not OperatorRole.PERFORMANCE_OPTIMIZATION:
        raise GovernedProposalFreezeError(
            "proposal freeze requires a performance_optimization operator",
        )
    if host_policy.kind is not AuthorityPrincipalKind.HOST_POLICY:
        raise GovernedProposalFreezeError(
            "proposal freeze authority principal must be host_policy",
        )
    if host_runtime.kind is not AuthorityPrincipalKind.HOST_RUNTIME:
        raise GovernedProposalFreezeError(
            "proposal freeze observation principal must be host_runtime",
        )


def validate_frozen_bindings(
    *,
    evaluation_regime: EvaluationRegime,
    evaluation_assignment: EvaluationAssignment,
    evaluation_assignment_candidate_scope: CandidateManifestScope | None,
    structural_split: StructuralSplitManifest,
    split: OptimizationSplit,
    leakage_audit: DecompositionLeakageAudit,
    problem_view: DecompositionProblemView,
    candidate_manifest: CandidateGenerationManifest,
    fixed_harness: CompiledHarnessInstance,
    proposal_policy: bytes,
    policy_checkpoint: bytes,
    proposal_artifacts: tuple[ProposalArtifact, ...],
    incumbent_artifact: IncumbentArtifact | None,
    host_policy: AuthorityPrincipal,
) -> SelectedTaskBinding:
    """Validate every exact binding before constructing the proposal freeze."""

    _validate_problem_view_candidate_bindings(
        evaluation_assignment=evaluation_assignment,
        evaluation_assignment_candidate_scope=evaluation_assignment_candidate_scope,
        leakage_audit=leakage_audit,
        problem_view=problem_view,
        candidate_manifest=candidate_manifest,
    )
    _validate_evaluation_manifest_bindings(
        evaluation_regime=evaluation_regime,
        evaluation_assignment=evaluation_assignment,
        structural_split=structural_split,
        fixed_harness=fixed_harness,
    )
    _validate_harness_projection_bindings(
        evaluation_assignment=evaluation_assignment,
        problem_view=problem_view,
        fixed_harness=fixed_harness,
    )
    _validate_generation_policy_bytes(
        candidate_manifest=candidate_manifest,
        proposal_policy=proposal_policy,
        policy_checkpoint=policy_checkpoint,
    )
    selected_task = _validate_selected_task(
        structural_split=structural_split,
        split=split,
        problem_view=problem_view,
    )
    proposal_candidate_ids = _validate_realized_proposal_artifacts(
        candidate_manifest=candidate_manifest,
        proposal_artifacts=proposal_artifacts,
    )
    _validate_incumbent_artifact(
        incumbent_artifact=incumbent_artifact,
        proposal_candidate_ids=proposal_candidate_ids,
        host_policy=host_policy,
    )
    return selected_task


def _validate_problem_view_candidate_bindings(
    *,
    evaluation_assignment: EvaluationAssignment,
    evaluation_assignment_candidate_scope: CandidateManifestScope | None,
    leakage_audit: DecompositionLeakageAudit,
    problem_view: DecompositionProblemView,
    candidate_manifest: CandidateGenerationManifest,
) -> None:
    if not leakage_audit.passed:
        raise GovernedProposalFreezeError(
            "proposal freeze requires a passed decomposition leakage audit",
        )
    if leakage_audit.problem_view_sha256 != problem_view.content_sha256:
        raise GovernedProposalFreezeError(
            "decomposition leakage audit does not bind the exact problem view",
        )
    if candidate_manifest.problem_view_sha256 != problem_view.content_sha256:
        raise GovernedProposalFreezeError(
            "candidate manifest does not bind the exact problem view",
        )
    if evaluation_assignment_candidate_scope is None:
        if evaluation_assignment.candidate_manifest_commitment != candidate_manifest.content_sha256:
            raise GovernedProposalFreezeError(
                "evaluation assignment candidate manifest does not match the proposal manifest",
            )
        return
    if evaluation_assignment.candidate_manifest_commitment != candidate_manifest_scope_commitment(
        evaluation_assignment_candidate_scope
    ):
        raise GovernedProposalFreezeError(
            "evaluation assignment candidate manifest does not match the candidate scope",
        )
    if candidate_manifest.content_sha256 not in evaluation_assignment_candidate_scope.candidate_manifest_sha256s:
        raise GovernedProposalFreezeError(
            "proposal candidate manifest is not a member of the evaluation assignment candidate scope",
        )


def _validate_evaluation_manifest_bindings(
    *,
    evaluation_regime: EvaluationRegime,
    evaluation_assignment: EvaluationAssignment,
    structural_split: StructuralSplitManifest,
    fixed_harness: CompiledHarnessInstance,
) -> None:
    try:
        validate_evaluation_regime_ref(evaluation_regime, evaluation_assignment.regime)
    except ValueError as error:
        raise GovernedProposalFreezeError(str(error)) from error
    if evaluation_assignment.split_manifest_commitment != structural_split.content_sha256:
        raise GovernedProposalFreezeError(
            "evaluation assignment structural split does not match the supplied manifest",
        )
    if evaluation_assignment.task_manifest_commitment != structural_split.task_manifest_sha256:
        raise GovernedProposalFreezeError(
            "evaluation assignment task manifest does not match the selected task manifest",
        )
    if evaluation_assignment.kernel_ref != fixed_harness.kernel_ref:
        raise GovernedProposalFreezeError(
            "evaluation assignment kernel does not match the compiled fixed harness",
        )


def _validate_harness_projection_bindings(
    *,
    evaluation_assignment: EvaluationAssignment,
    problem_view: DecompositionProblemView,
    fixed_harness: CompiledHarnessInstance,
) -> None:
    if problem_view.fixed_harness.kernel_ref != fixed_harness.kernel_ref:
        raise GovernedProposalFreezeError(
            "problem-view kernel does not match the compiled fixed harness",
        )
    if evaluation_assignment.harness_policy_commitment != problem_view.fixed_harness.harness_policy_sha256:
        raise GovernedProposalFreezeError(
            "evaluation assignment harness policy does not match the problem view",
        )
    if problem_view.fixed_harness.harness_policy_sha256 != fixed_harness_policy_sha256(fixed_harness):
        raise GovernedProposalFreezeError(
            "problem-view harness policy does not match the actual compiled fixed harness",
        )
    if problem_view.fixed_harness.aggregate_budget != fixed_harness.budget:
        raise GovernedProposalFreezeError(
            "problem-view aggregate budget does not match the compiled fixed harness",
        )
    if problem_view.task_id not in _fixed_harness_task_refs(fixed_harness):
        raise GovernedProposalFreezeError(
            "compiled fixed harness is not bound to the problem-view task",
        )


def _fixed_harness_task_refs(
    fixed_harness: CompiledHarnessInstance,
) -> set[str]:
    return {
        task_ref
        for binding in fixed_harness.bindings
        if isinstance(binding.configuration, TaskSourceBindingConfig)
        for task_ref in binding.configuration.task_refs
    }


def _validate_generation_policy_bytes(
    *,
    candidate_manifest: CandidateGenerationManifest,
    proposal_policy: bytes,
    policy_checkpoint: bytes,
) -> None:
    if hashlib.sha256(proposal_policy).hexdigest() != candidate_manifest.proposal_policy_sha256:
        raise GovernedProposalFreezeError(
            "exact proposal policy bytes do not match the candidate manifest",
        )
    if hashlib.sha256(policy_checkpoint).hexdigest() != candidate_manifest.policy_checkpoint_sha256:
        raise GovernedProposalFreezeError(
            "exact policy checkpoint bytes do not match the candidate manifest",
        )


def _validate_realized_proposal_artifacts(
    *,
    candidate_manifest: CandidateGenerationManifest,
    proposal_artifacts: tuple[ProposalArtifact, ...],
) -> set[str]:
    if not proposal_artifacts:
        raise GovernedProposalFreezeError(
            "proposal freeze requires at least one realized proposal artifact",
        )
    for artifact in proposal_artifacts:
        if artifact.reference.kind is not ProgramCandidateKind.PROPOSAL:
            raise GovernedProposalFreezeError(
                "realized proposal artifact must have proposal candidate kind",
            )
        if artifact.producer.kind not in {
            AuthorityPrincipalKind.MODEL,
            AuthorityPrincipalKind.OPTIMIZER,
        }:
            raise GovernedProposalFreezeError(
                "proposal artifact producer must be a model or optimizer",
            )
        if not artifact.producer_process_id or not artifact.invocation_id:
            raise GovernedProposalFreezeError(
                "proposal artifact requires exact producer process and invocation identities",
            )
        if hashlib.sha256(artifact.content).hexdigest() != artifact.reference.candidate_artifact_sha256:
            raise GovernedProposalFreezeError(
                f"proposal artifact bytes do not match {artifact.reference.candidate_id}",
            )
    expected = {coordinate.candidate_id: coordinate.coordinate_id for coordinate in candidate_manifest.coordinates}
    actual = {
        artifact.reference.candidate_id: (artifact.reference.generation_coordinate_id)
        for artifact in proposal_artifacts
    }
    if len(actual) != len(proposal_artifacts) or actual != expected:
        raise GovernedProposalFreezeError(
            "proposal artifacts do not form the exact realized candidate set",
        )
    return set(expected)


def _validate_incumbent_artifact(
    *,
    incumbent_artifact: IncumbentArtifact | None,
    proposal_candidate_ids: set[str],
    host_policy: AuthorityPrincipal,
) -> None:
    if incumbent_artifact is None:
        return
    if incumbent_artifact.reference.kind is not ProgramCandidateKind.INCUMBENT:
        raise GovernedProposalFreezeError(
            "frozen incumbent artifact must have incumbent candidate kind",
        )
    if incumbent_artifact.reference.candidate_id in proposal_candidate_ids:
        raise GovernedProposalFreezeError(
            "frozen incumbent must be distinct from every proposal candidate",
        )
    if incumbent_artifact.producer != host_policy:
        raise GovernedProposalFreezeError(
            "monolithic incumbent artifact must be authored by the freeze host policy",
        )
    if not incumbent_artifact.producer_process_id or not incumbent_artifact.invocation_id:
        raise GovernedProposalFreezeError(
            "incumbent artifact requires exact producer process and invocation identities",
        )
    if hashlib.sha256(incumbent_artifact.content).hexdigest() != incumbent_artifact.reference.candidate_artifact_sha256:
        raise GovernedProposalFreezeError(
            "incumbent artifact bytes do not match the frozen reference",
        )


def _validate_selected_task(
    *,
    structural_split: StructuralSplitManifest,
    split: OptimizationSplit,
    problem_view: DecompositionProblemView,
) -> SelectedTaskBinding:
    selected_split = {
        OptimizationSplit.TRAINING: structural_split.train,
        OptimizationSplit.DEVELOPMENT: structural_split.dev,
        OptimizationSplit.STRUCTURAL_HOLDOUT: structural_split.holdout,
    }.get(split)
    if selected_split is None:
        raise GovernedProposalFreezeError(
            "unsupported proposal-freeze split",
        )
    matches = tuple(item for item in selected_split.items if item.task_id == problem_view.task_id)
    if len(matches) != 1:
        raise GovernedProposalFreezeError(
            "problem view does not identify exactly one task in the selected structural split",
        )
    structural_item = matches[0]
    if problem_view.task_revision != structural_item.public_snapshot.definition_sha256:
        raise GovernedProposalFreezeError(
            "problem-view task revision does not match the selected public structural snapshot",
        )
    if problem_view.public_task_snapshot_sha256 != structural_item.public_task_snapshot_sha256:
        raise GovernedProposalFreezeError(
            "problem-view task snapshot does not match the selected public structural snapshot",
        )
    return SelectedTaskBinding(
        content_sha256=canonical_json_sha256(
            structural_item.model_dump(mode="json"),
        ),
        review_lineage_id=structural_item.review_lineage_id,
    )
