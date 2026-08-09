# ABOUTME: Authorizes one proposal compilation and canonical Harbor dispatch.
# ABOUTME: Persists the freeze-to-dispatch authority chain with complete origin closure.

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from aec_bench.contracts.authority import (
    AuthorityAction,
    AuthorityDecision,
    AuthorityEvent,
    AuthorityPrincipal,
    BasisKind,
    TaintLabel,
)
from aec_bench.contracts.harness_kernel import canonical_content_sha256
from aec_bench.contracts.program_proposal.candidate import ProgramCandidateRef
from aec_bench.contracts.program_proposal.study import MatchedEvaluationCoordinate
from aec_bench.experimentation.governance.authority_ledger import (
    AuthorityLedger,
    AuthorityLedgerError,
)
from aec_bench.experimentation.proposals.decomposition_optimization import (
    CandidateExecutionAssignment,
    DecompositionExecutionSchedule,
)
from aec_bench.experimentation.proposals.freezing import (
    GovernedProposalFreezeError,
    GovernedProposalFreezeResult,
    assert_proposal_freeze_authority,
)
from aec_bench.experimentation.proposals.harbor import (
    ProposalHarborDispatchInput,
    build_proposal_harbor_job_config,
)
from aec_bench.experimentation.proposals.program_compilation import (
    ProposalRunSessionBundle,
)
from aec_bench.experimentation.proposals.proposal_dispatch.binding_validation import (
    validate_dispatch_inputs,
    validate_freeze_compilation_join,
)
from aec_bench.experimentation.proposals.proposal_dispatch.contracts import (
    GovernedProposalDispatch,
    GovernedProposalDispatchAuthorization,
)
from aec_bench.experimentation.proposals.proposal_dispatch.errors import (
    ProposalDispatchGovernanceError,
)
from aec_bench.experimentation.proposals.proposal_dispatch.evidence import (
    basis_origins,
    origin_sha256s,
)
from aec_bench.experimentation.proposals.proposal_dispatch.replay import (
    replay_governed_proposal_dispatch,
)
from aec_bench.experimentation.proposals.proposal_dispatch.serialization import (
    canonical_json,
)
from aec_bench.experimentation.proposals.session_config import (
    ProposalSessionHostConfig,
    ProposalSessionHostConfigError,
    load_proposal_session_host_inputs,
)
from aec_bench.harness.harbor_dispatch import HarborDispatchError


def authorize_governed_proposal_dispatch(
    *,
    ledger: AuthorityLedger,
    dispatch_id: str,
    compile_event_id: str,
    provider_dispatch_event_id: str,
    governed_freeze: GovernedProposalFreezeResult,
    execution_schedule: DecompositionExecutionSchedule,
    execution_assignment: CandidateExecutionAssignment,
    evaluation_coordinate: MatchedEvaluationCoordinate,
    candidate_ref: ProgramCandidateRef,
    bundle: ProposalRunSessionBundle,
    host_config: ProposalSessionHostConfig,
    dispatch: ProposalHarborDispatchInput,
    harbor_job_config: Mapping[str, Any],
    host_runtime: AuthorityPrincipal,
    jobs_dir: Path | str = "jobs",
) -> GovernedProposalDispatchAuthorization:
    """Validate, observe, and authorize one exact proposal Harbor dispatch."""

    try:
        stored_freeze = assert_proposal_freeze_authority(
            ledger=ledger,
            result=governed_freeze,
        )
    except (
        AuthorityLedgerError,
        GovernedProposalFreezeError,
        ValueError,
    ) as error:
        raise ProposalDispatchGovernanceError(
            f"proposal freeze authority failed immediately before dispatch governance: {error}",
        ) from error

    (
        selected_candidate,
        selected_schedule,
        selected_assignment,
        selected_coordinate,
        selected_bundle,
        selected_host_config,
        selected_dispatch,
        runtime_principal,
    ) = validate_dispatch_inputs(
        candidate_ref=candidate_ref,
        execution_schedule=execution_schedule,
        execution_assignment=execution_assignment,
        evaluation_coordinate=evaluation_coordinate,
        bundle=bundle,
        host_config=host_config,
        dispatch=dispatch,
        host_runtime=host_runtime,
    )
    validate_freeze_compilation_join(
        governed_freeze=governed_freeze,
        stored_freeze=stored_freeze,
        candidate_ref=selected_candidate,
        execution_schedule=selected_schedule,
        execution_assignment=selected_assignment,
        evaluation_coordinate=selected_coordinate,
        bundle=selected_bundle,
    )

    try:
        loaded = load_proposal_session_host_inputs(
            selected_host_config.model_dump(mode="json"),
            environment_dir=(selected_dispatch.derived_task_path / "environment"),
        )
    except ProposalSessionHostConfigError as error:
        raise ProposalDispatchGovernanceError(
            f"proposal host configuration, runtime, or task identity is invalid: {error}",
        ) from error
    if loaded.bundle != selected_bundle:
        raise ProposalDispatchGovernanceError(
            "proposal session bundle differs from the exact host configuration",
        )
    if loaded.config != selected_host_config or loaded.derived_task_manifest != selected_dispatch.derived_task_manifest:
        raise ProposalDispatchGovernanceError(
            "proposal host configuration or task manifest differs from dispatch",
        )

    try:
        canonical_job = build_proposal_harbor_job_config(
            dispatch=selected_dispatch,
            jobs_dir=jobs_dir,
        )
        canonical_job_json = canonical_json(canonical_job)
        supplied_job_json = canonical_json(dict(harbor_job_config))
    except (HarborDispatchError, TypeError, ValueError) as error:
        raise ProposalDispatchGovernanceError(
            f"canonical Harbor job or task validation failed: {error}",
        ) from error
    if supplied_job_json != canonical_job_json:
        raise ProposalDispatchGovernanceError(
            "supplied proposal job differs from the canonical Harbor job",
        )

    scope = f"proposal-dispatch.{dispatch_id}"
    try:
        freeze_source_origins = basis_origins(
            ledger=ledger,
            references=stored_freeze.event.basis,
        )
        freeze_authority_basis = ledger.observe_model_basis(
            kind=BasisKind.AUTHORITY_EVENT,
            artifact_id=f"{scope}.freeze-authority",
            model=stored_freeze.event,
            producer=stored_freeze.event.principal,
            producer_process_id="aecbench.authority-ledger",
            observed_by=runtime_principal,
            channel="proposal-dispatch-governance",
            operation_id="proposal-dispatch.replay-freeze-authority",
            invocation_id=dispatch_id,
            parent_origin_sha256s=origin_sha256s(freeze_source_origins),
            operation_taint=(TaintLabel.RUNTIME_OBSERVED,),
        )
        execution_schedule_basis = ledger.observe_model_basis(
            kind=BasisKind.EVIDENCE,
            artifact_id=f"{scope}.execution-schedule",
            model=selected_schedule,
            producer=runtime_principal,
            producer_process_id="aecbench.decomposition-optimization",
            observed_by=runtime_principal,
            channel="proposal-dispatch-governance",
            operation_id="proposal-dispatch.observe-execution-schedule",
            invocation_id=dispatch_id,
            parent_origin_sha256s=origin_sha256s(
                (*freeze_source_origins, freeze_authority_basis.origin),
            ),
            operation_taint=(TaintLabel.RUNTIME_OBSERVED,),
        )
        execution_assignment_basis = ledger.observe_model_basis(
            kind=BasisKind.EVIDENCE,
            artifact_id=f"{scope}.execution-assignment",
            model=selected_assignment,
            producer=runtime_principal,
            producer_process_id="aecbench.decomposition-optimization",
            observed_by=runtime_principal,
            channel="proposal-dispatch-governance",
            operation_id="proposal-dispatch.observe-execution-assignment",
            invocation_id=dispatch_id,
            parent_origin_sha256s=(execution_schedule_basis.origin.content_sha256,),
            operation_taint=(TaintLabel.RUNTIME_OBSERVED,),
        )
        compilation_basis = ledger.observe_model_basis(
            kind=BasisKind.EVIDENCE,
            artifact_id=f"{scope}.compilation",
            model=selected_bundle.compilation,
            producer=runtime_principal,
            producer_process_id="aecbench.proposal-compiler",
            observed_by=runtime_principal,
            channel="proposal-dispatch-governance",
            operation_id="proposal-dispatch.observe-compilation",
            invocation_id=dispatch_id,
            parent_origin_sha256s=origin_sha256s(
                (
                    *freeze_source_origins,
                    freeze_authority_basis.origin,
                    execution_schedule_basis.origin,
                    execution_assignment_basis.origin,
                ),
            ),
            operation_taint=(TaintLabel.RUNTIME_OBSERVED,),
        )
        compile_event = AuthorityEvent(
            event_id=compile_event_id,
            principal=runtime_principal,
            action=AuthorityAction.COMPILE,
            decision=AuthorityDecision.GRANTED,
            subject_id=selected_bundle.compilation.compilation_id,
            subject_sha256=selected_bundle.compilation.content_sha256,
            basis=(
                freeze_authority_basis.reference,
                execution_schedule_basis.reference,
                execution_assignment_basis.reference,
                compilation_basis.reference,
            ),
            kernel_sha256=selected_bundle.compilation.kernel_sha256,
            reasons=("host runtime authorized the exact authority-frozen proposal compilation",),
            revalidation_triggers=(
                "bundle_change",
                "candidate_change",
                "execution_schedule_change",
                "execution_assignment_change",
                "freeze_authority_change",
                "task_identity_change",
            ),
        )
        record = GovernedProposalDispatch(
            dispatch_id=dispatch_id,
            candidate_ref=selected_candidate,
            evaluation_coordinate=selected_coordinate,
            execution_schedule_sha256=selected_schedule.content_sha256,
            execution_assignment_sha256=(selected_assignment.content_sha256),
            freeze_sha256=governed_freeze.freeze.content_sha256,
            freeze_authority_event_sha256=(stored_freeze.event.content_sha256),
            bundle=selected_bundle,
            bundle_sha256=selected_bundle.content_sha256,
            compilation_sha256=(selected_bundle.compilation.content_sha256),
            host_config=selected_host_config,
            host_config_sha256=canonical_content_sha256(
                selected_host_config.model_dump(mode="json"),
            ),
            runtime_archive_path=selected_host_config.runtime_archive_path,
            runtime_archive_sha256=(selected_host_config.runtime_archive_sha256),
            runtime_archive_content_sha256=(selected_host_config.runtime_archive_content_sha256),
            derived_task_path=str(selected_dispatch.derived_task_path),
            task_id=selected_dispatch.derived_task.task_id,
            task_revision=(selected_dispatch.derived_task_manifest.task_revision),
            source_task_package_sha256=(selected_dispatch.derived_task_manifest.source_task_package_sha256),
            derived_task_json=canonical_json(
                selected_dispatch.derived_task.model_dump(mode="json"),
            ),
            derived_task_sha256=canonical_content_sha256(
                selected_dispatch.derived_task.model_dump(mode="json"),
            ),
            derived_task_manifest=selected_dispatch.derived_task_manifest,
            harbor_job_config_json=canonical_job_json,
            harbor_job_config_sha256=canonical_content_sha256(canonical_job),
            compile_authority_event_sha256=compile_event.content_sha256,
        )
        stored_compile = ledger.issue_authority_event(compile_event)
        compile_basis_origins = basis_origins(
            ledger=ledger,
            references=stored_compile.event.basis,
        )
        compile_event_basis = ledger.observe_model_basis(
            kind=BasisKind.AUTHORITY_EVENT,
            artifact_id=f"{scope}.compile-authority",
            model=stored_compile.event,
            producer=runtime_principal,
            producer_process_id="aecbench.authority-ledger",
            observed_by=runtime_principal,
            channel="proposal-dispatch-governance",
            operation_id="proposal-dispatch.observe-compile-authority",
            invocation_id=dispatch_id,
            parent_origin_sha256s=origin_sha256s(compile_basis_origins),
            operation_taint=(TaintLabel.RUNTIME_OBSERVED,),
        )
        dispatch_basis = ledger.observe_model_basis(
            kind=BasisKind.EVIDENCE,
            artifact_id=f"{scope}.dispatch",
            model=record,
            producer=runtime_principal,
            producer_process_id="aecbench.proposal-dispatch",
            observed_by=runtime_principal,
            channel="proposal-dispatch-governance",
            operation_id="proposal-dispatch.observe-dispatch",
            invocation_id=dispatch_id,
            parent_origin_sha256s=origin_sha256s(
                (*compile_basis_origins, compile_event_basis.origin),
            ),
            operation_taint=(TaintLabel.RUNTIME_OBSERVED,),
        )
        provider_event = AuthorityEvent(
            event_id=provider_dispatch_event_id,
            principal=runtime_principal,
            action=AuthorityAction.PROVIDER_DISPATCH,
            decision=AuthorityDecision.GRANTED,
            subject_id=record.dispatch_id,
            subject_sha256=record.content_sha256,
            basis=(
                compile_event_basis.reference,
                dispatch_basis.reference,
            ),
            kernel_sha256=selected_bundle.compilation.kernel_sha256,
            reasons=("host runtime authorized the exact canonical proposal Harbor job",),
            revalidation_triggers=(
                "compile_authority_change",
                "harbor_job_change",
                "runtime_identity_change",
                "task_identity_change",
            ),
        )
        stored_provider = ledger.issue_authority_event(provider_event)
    except (AuthorityLedgerError, ValueError) as error:
        raise ProposalDispatchGovernanceError(
            f"proposal dispatch authority basis could not be persisted with complete origin closure: {error}",
        ) from error

    authorization = GovernedProposalDispatchAuthorization(
        dispatch=record,
        freeze_authority_event=stored_freeze.event,
        freeze_authority_basis=freeze_authority_basis.reference,
        freeze_authority_origin=freeze_authority_basis.origin,
        execution_schedule_basis=execution_schedule_basis.reference,
        execution_schedule_origin=execution_schedule_basis.origin,
        execution_assignment_basis=execution_assignment_basis.reference,
        execution_assignment_origin=execution_assignment_basis.origin,
        compilation_basis=compilation_basis.reference,
        compilation_origin=compilation_basis.origin,
        compile_event=stored_compile.event,
        compile_event_basis=compile_event_basis.reference,
        compile_event_origin=compile_event_basis.origin,
        dispatch_basis=dispatch_basis.reference,
        dispatch_origin=dispatch_basis.origin,
        provider_dispatch_event=stored_provider.event,
    )
    return replay_governed_proposal_dispatch(
        ledger=ledger,
        authorization=authorization,
    )
