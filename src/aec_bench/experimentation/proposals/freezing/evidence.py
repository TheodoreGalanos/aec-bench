# ABOUTME: Persists exact proposal-freeze inputs and reloads typed evidence from the ledger.
# ABOUTME: Maintains complete origin closure and candidate-taint labels for frozen artifacts.

from __future__ import annotations

import hashlib

from aec_bench.contracts.authority import (
    AuthorityPrincipal,
    AuthorityPrincipalKind,
    BasisKind,
    BasisReference,
    OperatorAuthority,
    TaintLabel,
)
from aec_bench.contracts.evaluation_plane import (
    CandidateManifestScope,
    EvaluationPlan,
)
from aec_bench.contracts.harness_instance import CompiledHarnessInstance
from aec_bench.contracts.harness_kernel import ContentAddressedModel
from aec_bench.contracts.program_proposal.candidate import CandidateGenerationManifest
from aec_bench.contracts.program_proposal.problem import DecompositionLeakageAudit, DecompositionProblemView
from aec_bench.contracts.proposal_execution_profile import (
    ProposalExecutionProfile,
)
from aec_bench.experimentation.governance.authority_ledger import (
    AuthorityLedger,
    StoredBasis,
)
from aec_bench.experimentation.proposals.freezing.contracts import (
    GovernedProposalFreezeError,
    IncumbentArtifact,
    ObservedInputBasis,
    ProposalArtifact,
)
from aec_bench.experimentation.proposals.structural_corpus import (
    StructuralSplitManifest,
)


def observe_input_basis(
    *,
    ledger: AuthorityLedger,
    scope: str,
    evaluation_plan: EvaluationPlan,
    evaluation_plan_candidate_scope: CandidateManifestScope | None,
    operator: OperatorAuthority,
    structural_split: StructuralSplitManifest,
    leakage_audit: DecompositionLeakageAudit,
    problem_view: DecompositionProblemView,
    candidate_manifest: CandidateGenerationManifest,
    fixed_harness: CompiledHarnessInstance,
    execution_profile: ProposalExecutionProfile | None,
    proposal_policy: bytes,
    policy_checkpoint: bytes,
    proposal_artifacts: tuple[ProposalArtifact, ...],
    incumbent_artifact: IncumbentArtifact | None,
    host_policy: AuthorityPrincipal,
    host_runtime: AuthorityPrincipal,
) -> ObservedInputBasis:
    """Observe all exact freeze inputs and return their basis join."""

    plan = _observe_model(
        ledger=ledger,
        artifact_id=(f"{scope}.evaluation-plan.{evaluation_plan.plan_id}"),
        model=evaluation_plan,
        producer=host_policy,
        host_runtime=host_runtime,
        operation_id="proposal-freeze.observe-evaluation-plan",
    )
    candidate_scope = (
        None
        if evaluation_plan_candidate_scope is None
        else _observe_model(
            ledger=ledger,
            artifact_id=(f"{scope}.candidate-manifest-scope.{evaluation_plan_candidate_scope.scope_id}"),
            model=evaluation_plan_candidate_scope,
            producer=host_policy,
            host_runtime=host_runtime,
            operation_id=("proposal-freeze.observe-candidate-manifest-scope"),
        )
    )
    authority = _observe_model(
        ledger=ledger,
        artifact_id=f"{scope}.operator-authority.{operator.operator_id}",
        model=operator,
        producer=host_policy,
        host_runtime=host_runtime,
        operation_id="proposal-freeze.observe-operator-authority",
    )
    structural = _observe_model(
        ledger=ledger,
        artifact_id=(f"{scope}.structural-split.{structural_split.manifest_id}"),
        model=structural_split,
        producer=host_policy,
        host_runtime=host_runtime,
        operation_id="proposal-freeze.observe-structural-split",
    )
    audit = _observe_model(
        ledger=ledger,
        artifact_id=f"{scope}.leakage-audit.{leakage_audit.audit_id}",
        model=leakage_audit,
        producer=host_policy,
        host_runtime=host_runtime,
        operation_id="proposal-freeze.observe-leakage-audit",
    )
    view = _observe_model(
        ledger=ledger,
        artifact_id=f"{scope}.problem-view.{problem_view.problem_id}",
        model=problem_view,
        producer=host_policy,
        host_runtime=host_runtime,
        operation_id="proposal-freeze.observe-problem-view",
    )
    manifest = _observe_model(
        ledger=ledger,
        artifact_id=(f"{scope}.candidate-manifest.{candidate_manifest.manifest_id}"),
        model=candidate_manifest,
        producer=host_policy,
        host_runtime=host_runtime,
        operation_id="proposal-freeze.observe-candidate-manifest",
    )
    harness = _observe_model(
        ledger=ledger,
        artifact_id=f"{scope}.fixed-harness.{fixed_harness.instance_id}",
        model=fixed_harness,
        producer=host_runtime,
        host_runtime=host_runtime,
        operation_id="proposal-freeze.observe-fixed-harness",
    )
    profile = (
        None
        if execution_profile is None
        else _observe_model(
            ledger=ledger,
            artifact_id=(f"{scope}.execution-profile.{execution_profile.content_sha256}"),
            model=execution_profile,
            producer=host_policy,
            host_runtime=host_runtime,
            operation_id="proposal-freeze.observe-execution-profile",
        )
    )
    policy = _observe_bytes(
        ledger=ledger,
        artifact_id=(f"{scope}.proposal-policy.{candidate_manifest.manifest_id}"),
        content=proposal_policy,
        producer=host_policy,
        host_runtime=host_runtime,
        operation_id="proposal-freeze.observe-proposal-policy",
    )
    checkpoint = _observe_bytes(
        ledger=ledger,
        artifact_id=(f"{scope}.policy-checkpoint.{candidate_manifest.manifest_id}"),
        content=policy_checkpoint,
        producer=host_policy,
        host_runtime=host_runtime,
        operation_id="proposal-freeze.observe-policy-checkpoint",
    )
    proposal_parents = (
        view.origin.content_sha256,
        manifest.origin.content_sha256,
        policy.origin.content_sha256,
        checkpoint.origin.content_sha256,
    )
    proposals = tuple(
        ledger.observe_basis(
            kind=BasisKind.EVIDENCE,
            artifact_id=(f"{scope}.proposal-artifact.{artifact.reference.candidate_id}"),
            content=artifact.content,
            producer=artifact.producer,
            producer_process_id=artifact.producer_process_id,
            observed_by=host_runtime,
            channel="proposal-freeze",
            operation_id="proposal-freeze.observe-proposal-artifact",
            invocation_id=artifact.invocation_id,
            parent_origin_sha256s=proposal_parents,
            operation_taint=_proposal_taint(artifact.producer),
        )
        for artifact in proposal_artifacts
    )
    incumbent = (
        None
        if incumbent_artifact is None
        else ledger.observe_basis(
            kind=BasisKind.EVIDENCE,
            artifact_id=(f"{scope}.incumbent-artifact.{incumbent_artifact.reference.candidate_id}"),
            content=incumbent_artifact.content,
            producer=incumbent_artifact.producer,
            producer_process_id=incumbent_artifact.producer_process_id,
            observed_by=host_runtime,
            channel="proposal-freeze",
            operation_id="proposal-freeze.observe-incumbent-artifact",
            invocation_id=incumbent_artifact.invocation_id,
            parent_origin_sha256s=(
                view.origin.content_sha256,
                harness.origin.content_sha256,
            ),
            operation_taint=(TaintLabel.RUNTIME_OBSERVED,),
        )
    )
    stored = (
        plan,
        *((candidate_scope,) if candidate_scope is not None else ()),
        authority,
        structural,
        audit,
        view,
        manifest,
        harness,
        *((profile,) if profile is not None else ()),
        policy,
        checkpoint,
        *proposals,
        *((incumbent,) if incumbent is not None else ()),
    )
    return ObservedInputBasis(
        evaluation_plan=plan.reference,
        evaluation_plan_candidate_scope=(None if candidate_scope is None else candidate_scope.reference),
        operator_authority=authority.reference,
        structural_split=structural.reference,
        leakage_audit=audit.reference,
        problem_view=view.reference,
        candidate_manifest=manifest.reference,
        fixed_harness=harness.reference,
        execution_profile=(None if profile is None else profile.reference),
        proposal_policy=policy.reference,
        policy_checkpoint=checkpoint.reference,
        proposal_artifacts=tuple(proposal.reference for proposal in proposals),
        incumbent_artifact=(None if incumbent is None else incumbent.reference),
        parent_origin_sha256s=tuple(item.origin.content_sha256 for item in stored),
    )


def load_evidence_model[ModelT: ContentAddressedModel](
    *,
    ledger: AuthorityLedger,
    reference: BasisReference,
    model_type: type[ModelT],
    label: str,
) -> ModelT:
    """Reload one exact typed evidence model."""

    stored = ledger.resolve_basis(reference)
    try:
        return model_type.model_validate_json(stored.content_path.read_bytes())
    except ValueError as error:
        raise GovernedProposalFreezeError(
            f"stored {label} basis has the wrong typed schema",
        ) from error


def _observe_model(
    *,
    ledger: AuthorityLedger,
    artifact_id: str,
    model: ContentAddressedModel,
    producer: AuthorityPrincipal,
    host_runtime: AuthorityPrincipal,
    operation_id: str,
) -> StoredBasis:
    return ledger.observe_model_basis(
        kind=BasisKind.EVIDENCE,
        artifact_id=artifact_id,
        model=model,
        producer=producer,
        producer_process_id="aecbench.proposal-freeze",
        observed_by=host_runtime,
        channel="proposal-freeze",
        operation_id=operation_id,
        invocation_id=model.content_sha256,
        operation_taint=(TaintLabel.RUNTIME_OBSERVED,),
    )


def _observe_bytes(
    *,
    ledger: AuthorityLedger,
    artifact_id: str,
    content: bytes,
    producer: AuthorityPrincipal,
    host_runtime: AuthorityPrincipal,
    operation_id: str,
) -> StoredBasis:
    return ledger.observe_basis(
        kind=BasisKind.EVIDENCE,
        artifact_id=artifact_id,
        content=content,
        producer=producer,
        producer_process_id="aecbench.proposal-freeze",
        observed_by=host_runtime,
        channel="proposal-freeze",
        operation_id=operation_id,
        invocation_id=hashlib.sha256(content).hexdigest(),
        operation_taint=(TaintLabel.RUNTIME_OBSERVED,),
    )


def _proposal_taint(
    producer: AuthorityPrincipal,
) -> tuple[TaintLabel, ...]:
    if producer.kind is AuthorityPrincipalKind.MODEL:
        return (
            TaintLabel.CANDIDATE_AUTHORED,
            TaintLabel.MODEL_REPORTED,
        )
    return (TaintLabel.CANDIDATE_AUTHORED,)
