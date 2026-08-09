# ABOUTME: Prepares, authorizes, reloads, and verifies exact critic-generation retirements.
# ABOUTME: Binds governed releases, declared historical coverage, human approval, and durable evidence.


from __future__ import annotations

from aec_bench.contracts.authority import (
    AuthorityAction,
    AuthorityDecision,
    AuthorityEvent,
    BasisReference,
)
from aec_bench.contracts.evaluation_plane import (
    CriticRole,
    CriticSpec,
)
from aec_bench.experimentation.governance.authority_ledger import (
    AuthorityLedger,
    AuthorityLedgerIntegrityError,
    StoredAuthorityEvent,
)

from .contracts import CriticGenerationRetirement, StoredCriticGenerationRetirement
from .evidence import (
    _critic_subject_id,
    _load_exact_retirement,
    _observe_authority_event_basis,
    _observe_critic_spec,
    _observe_governance_evidence,
    _require_acceptance_critic,
    _resolve_evaluation_outcomes,
    _resolve_human_approval,
    _resolve_promotion_authorities,
    _resolve_release_authority,
)


def prepare_critic_generation_retirement(
    *,
    ledger: AuthorityLedger,
    critic_spec: CriticSpec,
    release_authority: StoredAuthorityEvent,
    evaluation_outcomes: tuple[BasisReference, ...],
    promotion_authority_events: tuple[StoredAuthorityEvent, ...],
) -> CriticGenerationRetirement:
    """Resolve exact history and construct one critic-generation retirement subject."""
    selected = CriticSpec.model_validate(critic_spec.model_dump(mode="python"))
    released = _resolve_release_authority(
        ledger=ledger,
        stored=release_authority,
        critic_spec=selected,
    )
    _, outcome_sha256s = _resolve_evaluation_outcomes(
        ledger=ledger,
        references=evaluation_outcomes,
    )
    _, promotion_sha256s = _resolve_promotion_authorities(
        ledger=ledger,
        events=promotion_authority_events,
        critic_spec=selected,
    )
    return CriticGenerationRetirement(
        retirement_id=f"{_critic_subject_id(selected)}#retirement",
        critic_id=selected.critic_id,
        critic_version=selected.version,
        critic_generation_sha256=selected.content_sha256,
        release_authority_event_sha256=released.event.content_sha256,
        evaluation_outcome_sha256s=outcome_sha256s,
        promotion_authority_event_sha256s=promotion_sha256s,
    )


def retire_critic_generation(
    *,
    ledger: AuthorityLedger,
    critic_spec: CriticSpec,
    retirement: CriticGenerationRetirement,
    release_authority: StoredAuthorityEvent,
    evaluation_outcomes: tuple[BasisReference, ...],
    promotion_authority_events: tuple[StoredAuthorityEvent, ...],
    human_approval: BasisReference,
    event_id: str,
    kernel_sha256: str,
) -> StoredCriticGenerationRetirement:
    """Retire one critic under human authority over its exact declared history."""
    selected = CriticSpec.model_validate(critic_spec.model_dump(mode="python"))
    proposed = prepare_critic_generation_retirement(
        ledger=ledger,
        critic_spec=selected,
        release_authority=release_authority,
        evaluation_outcomes=evaluation_outcomes,
        promotion_authority_events=promotion_authority_events,
    )
    supplied = CriticGenerationRetirement.model_validate(retirement.model_dump(mode="python"))
    if supplied != proposed:
        raise AuthorityLedgerIntegrityError(
            "critic retirement does not match the exact critic release and historical coverage"
        )
    released = _resolve_release_authority(
        ledger=ledger,
        stored=release_authority,
        critic_spec=selected,
    )
    if released.event.kernel_sha256 != kernel_sha256:
        raise AuthorityLedgerIntegrityError("critic retirement kernel does not match its release authority")
    approval = _resolve_human_approval(
        ledger=ledger,
        reference=human_approval,
        action=AuthorityAction.RETIRE_CRITIC_GENERATION,
        subject_id=supplied.retirement_id,
        subject_sha256=supplied.content_sha256,
        mismatch_message="human approval does not match the exact critic retirement",
    )
    critic_basis = _observe_critic_spec(
        ledger=ledger,
        critic_spec=selected,
        event_id=event_id,
        operation_id="retire-critic-generation",
    )
    release_basis = _observe_authority_event_basis(
        ledger=ledger,
        stored=released,
        artifact_id=f"critic-retirement.{event_id}.release",
        operation_id="retire-critic-generation",
        invocation_id=event_id,
    )
    outcome_bases, _ = _resolve_evaluation_outcomes(
        ledger=ledger,
        references=evaluation_outcomes,
    )
    promotions, _ = _resolve_promotion_authorities(
        ledger=ledger,
        events=promotion_authority_events,
        critic_spec=selected,
    )
    promotion_bases = tuple(
        _observe_authority_event_basis(
            ledger=ledger,
            stored=promotion,
            artifact_id=f"critic-retirement.{event_id}.promotion.{index}",
            operation_id="retire-critic-generation",
            invocation_id=event_id,
        )
        for index, promotion in enumerate(promotions)
    )
    retirement_basis = _observe_governance_evidence(
        ledger=ledger,
        artifact_id=f"critic-retirement.{event_id}",
        model=supplied,
        operation_id="retire-critic-generation",
        invocation_id=event_id,
    )
    event = AuthorityEvent(
        event_id=event_id,
        principal=approval.principal,
        action=AuthorityAction.RETIRE_CRITIC_GENERATION,
        decision=AuthorityDecision.GRANTED,
        subject_id=supplied.retirement_id,
        subject_sha256=supplied.content_sha256,
        basis=tuple(
            [
                human_approval,
                critic_basis.reference,
                release_basis.reference,
                retirement_basis.reference,
                *(basis.reference for basis in outcome_bases),
                *(basis.reference for basis in promotion_bases),
            ]
        ),
        kernel_sha256=kernel_sha256,
        critic_generation_sha256=selected.content_sha256,
        reasons=(f"human retired exact {selected.role.value} critic generation with complete declared history",),
        revalidation_triggers=(("acceptance_manifest_reveal_due",) if selected.role is CriticRole.ACCEPTANCE else ()),
    )
    authority = ledger.issue_authority_event(event)
    return StoredCriticGenerationRetirement(
        retirement=supplied,
        evidence=retirement_basis,
        authority_event=authority,
    )


def retire_acceptance_critic_generation(
    *,
    ledger: AuthorityLedger,
    critic_spec: CriticSpec,
    retirement: CriticGenerationRetirement,
    release_authority: StoredAuthorityEvent,
    evaluation_outcomes: tuple[BasisReference, ...],
    promotion_authority_events: tuple[StoredAuthorityEvent, ...],
    human_approval: BasisReference,
    event_id: str,
    kernel_sha256: str,
) -> StoredCriticGenerationRetirement:
    """Retire one escrowed acceptance critic under exact human authority."""
    selected = _require_acceptance_critic(critic_spec)
    return retire_critic_generation(
        ledger=ledger,
        critic_spec=selected,
        retirement=retirement,
        release_authority=release_authority,
        evaluation_outcomes=evaluation_outcomes,
        promotion_authority_events=promotion_authority_events,
        human_approval=human_approval,
        event_id=event_id,
        kernel_sha256=kernel_sha256,
    )


def load_critic_generation_retirement(
    *,
    ledger: AuthorityLedger,
    event_id: str,
    content_sha256: str,
) -> StoredCriticGenerationRetirement:
    """Reload and independently verify one exact retirement authority chain."""
    stored = ledger.resolve_authority_event(
        event_id=event_id,
        content_sha256=content_sha256,
    )
    return _load_exact_retirement(
        ledger=ledger,
        stored=stored,
    )
