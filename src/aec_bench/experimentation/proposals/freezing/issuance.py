# ABOUTME: Validates, persists, authorizes, and immediately replays one exact proposal freeze.
# ABOUTME: Keeps full plan and proposal bytes ledger-confined before candidate evaluation begins.

from __future__ import annotations

from aec_bench.contracts.authority import (
    AuthorityAction,
    AuthorityDecision,
    AuthorityEvent,
    AuthorityPrincipal,
    BasisKind,
    OperatorAuthority,
    TaintLabel,
)
from aec_bench.contracts.evaluation_plane import (
    CandidateManifestScope,
    EvaluationPlan,
)
from aec_bench.contracts.harness_instance import CompiledHarnessInstance
from aec_bench.contracts.program_proposal.candidate import CandidateGenerationManifest, ProgramCandidateRef
from aec_bench.contracts.program_proposal.freeze import ProposalFreeze
from aec_bench.contracts.program_proposal.problem import DecompositionLeakageAudit, DecompositionProblemView
from aec_bench.contracts.program_proposal.types import OptimizationSplit
from aec_bench.contracts.proposal_execution_profile import (
    ProposalExecutionProfile,
)
from aec_bench.experimentation.governance.authority_ledger import (
    AuthorityLedger,
    AuthorityLedgerError,
)
from aec_bench.experimentation.governance.standing_monitors import (
    replay_scheduled_basis,
    schedule_basis_replay,
)
from aec_bench.experimentation.proposals.freezing.contracts import (
    GovernedProposalFreezeError,
    GovernedProposalFreezeResult,
    IncumbentArtifact,
    ProposalArtifact,
    ProposalFreezeBasis,
)
from aec_bench.experimentation.proposals.freezing.evidence import (
    observe_input_basis,
)
from aec_bench.experimentation.proposals.freezing.validation import (
    validate_frozen_bindings,
    validate_principals,
)
from aec_bench.experimentation.proposals.structural_corpus import (
    StructuralSplitManifest,
)


def issue_governed_proposal_freeze(
    *,
    ledger: AuthorityLedger,
    freeze_id: str,
    event_id: str,
    replay_id: str,
    due_cycle_index: int,
    evaluation_plan: EvaluationPlan,
    evaluation_plan_candidate_scope: CandidateManifestScope | None = None,
    operator_authority: OperatorAuthority,
    structural_split: StructuralSplitManifest,
    split: OptimizationSplit,
    leakage_audit: DecompositionLeakageAudit,
    problem_view: DecompositionProblemView,
    candidate_manifest: CandidateGenerationManifest,
    fixed_harness: CompiledHarnessInstance,
    execution_profile: ProposalExecutionProfile | None = None,
    proposal_policy: bytes,
    policy_checkpoint: bytes,
    proposal_artifacts: tuple[ProposalArtifact, ...],
    host_policy: AuthorityPrincipal,
    host_runtime: AuthorityPrincipal,
    incumbent_artifact: IncumbentArtifact | None = None,
) -> GovernedProposalFreezeResult:
    """Validate, persist, authorize, and immediately replay one exact proposal freeze."""

    try:
        plan = EvaluationPlan.model_validate(
            evaluation_plan.model_dump(mode="python"),
        )
        candidate_scope = (
            None
            if evaluation_plan_candidate_scope is None
            else CandidateManifestScope.model_validate(
                evaluation_plan_candidate_scope.model_dump(mode="python"),
            )
        )
        operator = OperatorAuthority.model_validate(
            operator_authority.model_dump(mode="python"),
        )
        structural = StructuralSplitManifest.model_validate(
            structural_split.model_dump(mode="python"),
        )
        audit = DecompositionLeakageAudit.model_validate(
            leakage_audit.model_dump(mode="python"),
        )
        view = DecompositionProblemView.model_validate(
            problem_view.model_dump(mode="python"),
        )
        manifest = CandidateGenerationManifest.model_validate(
            candidate_manifest.model_dump(mode="python"),
        )
        harness = CompiledHarnessInstance.model_validate(
            fixed_harness.model_dump(mode="python"),
        )
        profile = (
            None
            if execution_profile is None
            else ProposalExecutionProfile.model_validate(
                execution_profile.model_dump(mode="python"),
            )
        )
        policy_principal = AuthorityPrincipal.model_validate(
            host_policy.model_dump(mode="python"),
        )
        runtime_principal = AuthorityPrincipal.model_validate(
            host_runtime.model_dump(mode="python"),
        )
        artifacts = tuple(
            ProposalArtifact(
                reference=ProgramCandidateRef.model_validate(
                    artifact.reference.model_dump(mode="python"),
                ),
                content=bytes(artifact.content),
                producer=AuthorityPrincipal.model_validate(
                    artifact.producer.model_dump(mode="python"),
                ),
                producer_process_id=artifact.producer_process_id,
                invocation_id=artifact.invocation_id,
            )
            for artifact in proposal_artifacts
        )
        incumbent = (
            None
            if incumbent_artifact is None
            else IncumbentArtifact(
                reference=ProgramCandidateRef.model_validate(
                    incumbent_artifact.reference.model_dump(mode="python"),
                ),
                content=bytes(incumbent_artifact.content),
                producer=AuthorityPrincipal.model_validate(
                    incumbent_artifact.producer.model_dump(mode="python"),
                ),
                producer_process_id=(incumbent_artifact.producer_process_id),
                invocation_id=incumbent_artifact.invocation_id,
            )
        )
    except ValueError as error:
        raise GovernedProposalFreezeError(
            f"proposal freeze input contract is invalid: {error}",
        ) from error

    validate_principals(
        operator=operator,
        host_policy=policy_principal,
        host_runtime=runtime_principal,
    )
    if profile is not None and (
        profile.required_kernel_id != harness.kernel_ref.kernel_id
        or profile.required_kernel_version != harness.kernel_ref.version
    ):
        raise GovernedProposalFreezeError(
            "proposal execution profile requires a different fixed-harness kernel",
        )
    selected_task = validate_frozen_bindings(
        evaluation_plan=plan,
        evaluation_plan_candidate_scope=candidate_scope,
        structural_split=structural,
        split=split,
        leakage_audit=audit,
        problem_view=view,
        candidate_manifest=manifest,
        fixed_harness=harness,
        proposal_policy=proposal_policy,
        policy_checkpoint=policy_checkpoint,
        proposal_artifacts=artifacts,
        incumbent_artifact=incumbent,
        host_policy=policy_principal,
    )

    try:
        freeze = ProposalFreeze(
            freeze_id=freeze_id,
            evaluation_plan_ref=plan.ref,
            evaluation_plan_candidate_manifest_sha256=(plan.candidate_manifest_sha256),
            evaluation_plan_candidate_scope=candidate_scope,
            structural_split_sha256=structural.content_sha256,
            selected_structural_item_sha256=selected_task.content_sha256,
            selected_review_lineage_id=selected_task.review_lineage_id,
            fixed_harness_ref=harness.ref,
            execution_profile_sha256=(None if profile is None else profile.content_sha256),
            operator_authority=operator,
            split=split,
            leakage_audit=audit,
            problem_view=view,
            candidate_manifest=manifest,
            proposal_policy_sha256=manifest.proposal_policy_sha256,
            policy_checkpoint_sha256=manifest.policy_checkpoint_sha256,
            realized_candidates=tuple(artifact.reference for artifact in artifacts),
            incumbent_candidate=(None if incumbent is None else incumbent.reference),
            proposal_set_closed=True,
            late_candidates_permitted=False,
        )
    except ValueError as error:
        raise GovernedProposalFreezeError(
            f"proposal freeze does not bind the exact realized candidate set: {error}",
        ) from error

    try:
        scope = f"proposal-freeze.{freeze.freeze_id}"
        observed = observe_input_basis(
            ledger=ledger,
            scope=scope,
            evaluation_plan=plan,
            evaluation_plan_candidate_scope=candidate_scope,
            operator=operator,
            structural_split=structural,
            leakage_audit=audit,
            problem_view=view,
            candidate_manifest=manifest,
            fixed_harness=harness,
            execution_profile=profile,
            proposal_policy=proposal_policy,
            policy_checkpoint=policy_checkpoint,
            proposal_artifacts=artifacts,
            incumbent_artifact=incumbent,
            host_policy=policy_principal,
            host_runtime=runtime_principal,
        )
        freeze_basis = ledger.observe_model_basis(
            kind=BasisKind.EVIDENCE,
            artifact_id=f"{scope}.freeze",
            model=freeze,
            producer=policy_principal,
            producer_process_id="aecbench.proposal-freeze",
            observed_by=runtime_principal,
            channel="proposal-freeze",
            operation_id="proposal-freeze.close-set",
            invocation_id=freeze.content_sha256,
            parent_origin_sha256s=observed.parent_origin_sha256s,
            operation_taint=(TaintLabel.RUNTIME_OBSERVED,),
        )
        complete_basis = ProposalFreezeBasis(
            evaluation_plan=observed.evaluation_plan,
            evaluation_plan_candidate_scope=(observed.evaluation_plan_candidate_scope),
            operator_authority=observed.operator_authority,
            structural_split=observed.structural_split,
            leakage_audit=observed.leakage_audit,
            problem_view=observed.problem_view,
            candidate_manifest=observed.candidate_manifest,
            fixed_harness=observed.fixed_harness,
            execution_profile=observed.execution_profile,
            proposal_policy=observed.proposal_policy,
            policy_checkpoint=observed.policy_checkpoint,
            proposal_artifacts=observed.proposal_artifacts,
            incumbent_artifact=observed.incumbent_artifact,
            freeze=freeze_basis.reference,
        )
        event = AuthorityEvent(
            event_id=event_id,
            principal=policy_principal,
            action=AuthorityAction.PROPOSAL_FREEZE,
            decision=AuthorityDecision.GRANTED,
            subject_id=freeze.freeze_id,
            subject_sha256=freeze.content_sha256,
            basis=complete_basis.references,
            kernel_ref=plan.kernel_ref,
            reasons=("host policy froze the exact preregistered proposal set before evaluation",),
            revalidation_triggers=(
                "basis_replay_due",
                "candidate_manifest_change",
                "evaluation_plan_change",
                "fixed_harness_change",
                "structural_split_change",
                *(("execution_profile_change",) if profile is not None else ()),
            ),
        )
        stored = ledger.issue_authority_event(event)
        replay_requirement = schedule_basis_replay(
            ledger=ledger,
            replay_id=replay_id,
            authority_event_id=stored.event.event_id,
            authority_event_sha256=stored.event.content_sha256,
            due_cycle_index=due_cycle_index,
        )
        replay_observation = replay_scheduled_basis(
            ledger=ledger,
            requirement=replay_requirement,
        )
        if not replay_observation.closure_complete:
            raise GovernedProposalFreezeError(
                "proposal freeze basis did not close during immediate replay",
            )
        return GovernedProposalFreezeResult(
            freeze=freeze,
            basis=complete_basis,
            authority_event=stored.event,
            replay_requirement=replay_requirement,
            replay_observation=replay_observation,
        )
    except AuthorityLedgerError as error:
        raise GovernedProposalFreezeError(
            f"proposal freeze basis could not be persisted or resolved: {error}",
        ) from error
