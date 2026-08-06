# ABOUTME: Replays governed proposal-dispatch evidence and authority chains from the ledger.
# ABOUTME: Revalidates exact bases, origins, events, compilation, assignment, and dispatch records.

from __future__ import annotations

from aec_bench.contracts.authority import (
    AuthorityAction,
    AuthorityDecision,
    AuthorityEvent,
    AuthorityPrincipalKind,
    BasisReference,
    OriginStamp,
)
from aec_bench.contracts.proposal_execution.compilation import ProposalCompilationSuccess
from aec_bench.meta_harness.authority_ledger import (
    AuthorityLedger,
    AuthorityLedgerError,
)
from aec_bench.meta_harness.decomposition_optimization import (
    CandidateExecutionAssignment,
    DecompositionExecutionSchedule,
)
from aec_bench.meta_harness.proposal_dispatch.contracts import (
    GovernedProposalDispatch,
    GovernedProposalDispatchAuthorization,
)
from aec_bench.meta_harness.proposal_dispatch.errors import (
    ProposalDispatchGovernanceError,
)
from aec_bench.meta_harness.proposal_dispatch.evidence import (
    assert_exact_origin_parents,
    basis_origins,
    origin_sha256s,
    resolve_event_basis,
    resolve_evidence_model,
    resolve_exact_event,
)


def replay_governed_proposal_dispatch(
    *,
    ledger: AuthorityLedger,
    authorization: GovernedProposalDispatchAuthorization,
) -> GovernedProposalDispatchAuthorization:
    """Re-resolve every basis, origin, and authority event in one dispatch chain."""

    normalized = _normalize_authorization(authorization)
    _validate_authorization_shape(normalized)
    try:
        freeze_source_origins = basis_origins(
            ledger=ledger,
            references=normalized.freeze_authority_event.basis,
        )
        freeze_basis, freeze_event = resolve_event_basis(
            ledger=ledger,
            reference=normalized.freeze_authority_basis,
            expected_origin=normalized.freeze_authority_origin,
            expected_event=normalized.freeze_authority_event,
        )
        assert_exact_origin_parents(
            origin=freeze_basis.origin,
            expected=origin_sha256s(freeze_source_origins),
            label="freeze authority",
        )
        ledger.resolve_authority_event(
            event_id=freeze_event.event_id,
            content_sha256=freeze_event.content_sha256,
        )

        schedule_basis, schedule = resolve_evidence_model(
            ledger=ledger,
            reference=normalized.execution_schedule_basis,
            expected_origin=normalized.execution_schedule_origin,
            model_type=DecompositionExecutionSchedule,
            label="decomposition execution schedule",
        )
        if schedule.content_sha256 != normalized.dispatch.execution_schedule_sha256:
            raise ProposalDispatchGovernanceError(
                "replayed execution schedule differs from the governed dispatch",
            )
        assert_exact_origin_parents(
            origin=schedule_basis.origin,
            expected=origin_sha256s(
                (*freeze_source_origins, freeze_basis.origin),
            ),
            label="decomposition execution schedule",
        )
        assignment_basis, assignment = resolve_evidence_model(
            ledger=ledger,
            reference=normalized.execution_assignment_basis,
            expected_origin=normalized.execution_assignment_origin,
            model_type=CandidateExecutionAssignment,
            label="candidate execution assignment",
        )
        if (
            assignment.content_sha256 != normalized.dispatch.execution_assignment_sha256
            or assignment not in schedule.assignments
            or assignment.candidate != normalized.dispatch.candidate_ref
            or assignment.coordinate != normalized.dispatch.evaluation_coordinate
        ):
            raise ProposalDispatchGovernanceError(
                "replayed execution assignment differs from the governed dispatch",
            )
        assert_exact_origin_parents(
            origin=assignment_basis.origin,
            expected=(schedule_basis.origin.content_sha256,),
            label="candidate execution assignment",
        )

        compilation_basis, compilation = resolve_evidence_model(
            ledger=ledger,
            reference=normalized.compilation_basis,
            expected_origin=normalized.compilation_origin,
            model_type=ProposalCompilationSuccess,
            label="proposal compilation",
        )
        if compilation != normalized.dispatch.bundle.compilation:
            raise ProposalDispatchGovernanceError(
                "replayed proposal compilation differs from the governed dispatch",
            )
        assert_exact_origin_parents(
            origin=compilation_basis.origin,
            expected=origin_sha256s(
                (
                    *freeze_source_origins,
                    freeze_basis.origin,
                    schedule_basis.origin,
                    assignment_basis.origin,
                ),
            ),
            label="proposal compilation",
        )

        stored_compile = resolve_exact_event(
            ledger=ledger,
            expected=normalized.compile_event,
            label="compile",
        )
        compile_basis_origins = basis_origins(
            ledger=ledger,
            references=stored_compile.event.basis,
        )
        compile_event_basis, compile_basis_event = resolve_event_basis(
            ledger=ledger,
            reference=normalized.compile_event_basis,
            expected_origin=normalized.compile_event_origin,
            expected_event=stored_compile.event,
        )
        if compile_basis_event != normalized.compile_event:
            raise ProposalDispatchGovernanceError(
                "compile authority event drifted from its exact event basis",
            )
        assert_exact_origin_parents(
            origin=compile_event_basis.origin,
            expected=origin_sha256s(compile_basis_origins),
            label="compile authority",
        )

        dispatch_basis, dispatch_record = resolve_evidence_model(
            ledger=ledger,
            reference=normalized.dispatch_basis,
            expected_origin=normalized.dispatch_origin,
            model_type=GovernedProposalDispatch,
            label="governed proposal dispatch",
        )
        if dispatch_record != normalized.dispatch:
            raise ProposalDispatchGovernanceError(
                "replayed proposal dispatch differs from the exact governed record",
            )
        assert_exact_origin_parents(
            origin=dispatch_basis.origin,
            expected=origin_sha256s(
                (*compile_basis_origins, compile_event_basis.origin),
            ),
            label="governed proposal dispatch",
        )

        stored_provider = resolve_exact_event(
            ledger=ledger,
            expected=normalized.provider_dispatch_event,
            label="provider dispatch",
        )
        ledger.validate_basis_closure(stored_provider.event)
    except ProposalDispatchGovernanceError:
        raise
    except AuthorityLedgerError as error:
        raise ProposalDispatchGovernanceError(
            f"proposal dispatch basis or origin closure cannot be replayed: {error}",
        ) from error
    return normalized


def _normalize_authorization(
    authorization: GovernedProposalDispatchAuthorization,
) -> GovernedProposalDispatchAuthorization:
    try:
        return GovernedProposalDispatchAuthorization(
            dispatch=GovernedProposalDispatch.model_validate(
                authorization.dispatch.model_dump(mode="python"),
            ),
            freeze_authority_event=AuthorityEvent.model_validate(
                authorization.freeze_authority_event.model_dump(mode="python"),
            ),
            freeze_authority_basis=BasisReference.model_validate(
                authorization.freeze_authority_basis.model_dump(mode="python"),
            ),
            freeze_authority_origin=OriginStamp.model_validate(
                authorization.freeze_authority_origin.model_dump(mode="python"),
            ),
            execution_schedule_basis=BasisReference.model_validate(
                authorization.execution_schedule_basis.model_dump(mode="python"),
            ),
            execution_schedule_origin=OriginStamp.model_validate(
                authorization.execution_schedule_origin.model_dump(mode="python"),
            ),
            execution_assignment_basis=BasisReference.model_validate(
                authorization.execution_assignment_basis.model_dump(mode="python"),
            ),
            execution_assignment_origin=OriginStamp.model_validate(
                authorization.execution_assignment_origin.model_dump(mode="python"),
            ),
            compilation_basis=BasisReference.model_validate(
                authorization.compilation_basis.model_dump(mode="python"),
            ),
            compilation_origin=OriginStamp.model_validate(
                authorization.compilation_origin.model_dump(mode="python"),
            ),
            compile_event=AuthorityEvent.model_validate(
                authorization.compile_event.model_dump(mode="python"),
            ),
            compile_event_basis=BasisReference.model_validate(
                authorization.compile_event_basis.model_dump(mode="python"),
            ),
            compile_event_origin=OriginStamp.model_validate(
                authorization.compile_event_origin.model_dump(mode="python"),
            ),
            dispatch_basis=BasisReference.model_validate(
                authorization.dispatch_basis.model_dump(mode="python"),
            ),
            dispatch_origin=OriginStamp.model_validate(
                authorization.dispatch_origin.model_dump(mode="python"),
            ),
            provider_dispatch_event=AuthorityEvent.model_validate(
                authorization.provider_dispatch_event.model_dump(mode="python"),
            ),
        )
    except ValueError as error:
        raise ProposalDispatchGovernanceError(
            f"proposal dispatch authority event drift or contract error: {error}",
        ) from error


def _validate_authorization_shape(
    authorization: GovernedProposalDispatchAuthorization,
) -> None:
    record = authorization.dispatch
    scope = f"proposal-dispatch.{record.dispatch_id}"
    expected_ids = {
        authorization.freeze_authority_basis: f"{scope}.freeze-authority",
        authorization.execution_schedule_basis: f"{scope}.execution-schedule",
        authorization.execution_assignment_basis: (f"{scope}.execution-assignment"),
        authorization.compilation_basis: f"{scope}.compilation",
        authorization.compile_event_basis: f"{scope}.compile-authority",
        authorization.dispatch_basis: f"{scope}.dispatch",
    }
    for reference, artifact_id in expected_ids.items():
        if reference.artifact_id != artifact_id:
            raise ProposalDispatchGovernanceError(
                "proposal dispatch basis identity drifted from its exact scope",
            )
    _validate_freeze_event(authorization)
    _validate_compile_event(authorization)
    _validate_provider_event(authorization)


def _validate_freeze_event(
    authorization: GovernedProposalDispatchAuthorization,
) -> None:
    record = authorization.dispatch
    freeze_event = authorization.freeze_authority_event
    compilation = record.bundle.compilation
    if (
        freeze_event.action is not AuthorityAction.PROPOSAL_FREEZE
        or freeze_event.decision is not AuthorityDecision.GRANTED
        or freeze_event.subject_id != compilation.proposal_freeze.freeze_id
        or freeze_event.subject_sha256 != record.freeze_sha256
        or freeze_event.content_sha256 != record.freeze_authority_event_sha256
    ):
        raise ProposalDispatchGovernanceError(
            "proposal freeze authority event drifted from the governed dispatch",
        )


def _validate_compile_event(
    authorization: GovernedProposalDispatchAuthorization,
) -> None:
    record = authorization.dispatch
    compilation = record.bundle.compilation
    compile_event = authorization.compile_event
    if (
        compile_event.action is not AuthorityAction.COMPILE
        or compile_event.decision is not AuthorityDecision.GRANTED
        or compile_event.principal.kind is not AuthorityPrincipalKind.HOST_RUNTIME
        or compile_event.subject_id != compilation.compilation_id
        or compile_event.subject_sha256 != compilation.content_sha256
        or compile_event.kernel_sha256 != compilation.kernel_sha256
        or compile_event.basis
        != (
            authorization.freeze_authority_basis,
            authorization.compilation_basis,
            authorization.execution_assignment_basis,
            authorization.execution_schedule_basis,
        )
        or compile_event.content_sha256 != record.compile_authority_event_sha256
    ):
        raise ProposalDispatchGovernanceError(
            "compile authority event drifted from the governed dispatch",
        )


def _validate_provider_event(
    authorization: GovernedProposalDispatchAuthorization,
) -> None:
    record = authorization.dispatch
    compilation = record.bundle.compilation
    compile_event = authorization.compile_event
    provider_event = authorization.provider_dispatch_event
    if (
        provider_event.action is not AuthorityAction.PROVIDER_DISPATCH
        or provider_event.decision is not AuthorityDecision.GRANTED
        or provider_event.principal != compile_event.principal
        or provider_event.subject_id != record.dispatch_id
        or provider_event.subject_sha256 != record.content_sha256
        or provider_event.kernel_sha256 != compilation.kernel_sha256
        or provider_event.basis
        != (
            authorization.compile_event_basis,
            authorization.dispatch_basis,
        )
    ):
        raise ProposalDispatchGovernanceError(
            "provider dispatch authority event drifted from the governed dispatch",
        )
