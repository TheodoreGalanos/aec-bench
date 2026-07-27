# ABOUTME: Prepares, authorizes, reloads, and closes retirement-bound acceptance-manifest reveals.
# ABOUTME: Enforces escrow recovery, exact historical coverage, and eventual auditability.


from __future__ import annotations

from pydantic import JsonValue

from aec_bench.contracts.authority import (
    AuthorityAction,
    AuthorityDecision,
    AuthorityEvent,
    BasisReference,
)
from aec_bench.contracts.evaluation_plane import (
    AcceptanceManifestReveal,
    CriticSpec,
)
from aec_bench.meta_harness.acceptance_manifest_escrow import (
    load_acceptance_manifest_escrow,
)
from aec_bench.meta_harness.authority_ledger import (
    AuthorityLedger,
    AuthorityLedgerIntegrityError,
    StoredAuthorityEvent,
)

from .contracts import (
    AcceptanceAuditClosure,
    StoredAcceptanceManifestReveal,
)
from .evidence import (
    _event_evaluation_outcomes,
    _event_has_exact_authority_basis,
    _event_promotion_authorities,
    _find_evidence_model,
    _load_exact_retirement,
    _observe_authority_event_basis,
    _observe_critic_spec,
    _observe_governance_evidence,
    _require_acceptance_critic,
    _require_event_human_authority,
    _require_historical_coverage,
    _require_retirement_for_critic,
    _resolve_evaluation_outcomes,
    _resolve_human_approval,
    _resolve_promotion_authorities,
    _reveal_subject_id,
)


def prepare_acceptance_manifest_reveal(
    *,
    ledger: AuthorityLedger,
    critic_spec: CriticSpec,
    retirement_authority: StoredAuthorityEvent,
    case_manifest: JsonValue | None = None,
    scoring_policy: JsonValue | None = None,
    salt: str | None = None,
    evaluation_outcomes: tuple[BasisReference, ...],
    promotion_authority_events: tuple[StoredAuthorityEvent, ...],
) -> AcceptanceManifestReveal:
    """Construct a reveal from durable escrow after exact retirement and history resolve."""
    selected = _require_acceptance_critic(critic_spec)
    escrow = load_acceptance_manifest_escrow(
        ledger=ledger,
        critic_spec=selected,
    )
    supplied_material = (
        case_manifest is not None,
        scoring_policy is not None,
        salt is not None,
    )
    if any(supplied_material) and not all(supplied_material):
        raise AuthorityLedgerIntegrityError(
            "acceptance manifest reveal material must be supplied completely or loaded from escrow"
        )
    selected_case_manifest = escrow.payload.case_manifest if case_manifest is None else case_manifest
    selected_scoring_policy = escrow.payload.scoring_policy if scoring_policy is None else scoring_policy
    selected_salt = escrow.payload.salt if salt is None else salt
    retired = _load_exact_retirement(
        ledger=ledger,
        stored=retirement_authority,
    )
    _require_retirement_for_critic(retired.retirement, selected)
    _, outcome_sha256s = _resolve_evaluation_outcomes(
        ledger=ledger,
        references=evaluation_outcomes,
    )
    _, promotion_sha256s = _resolve_promotion_authorities(
        ledger=ledger,
        events=promotion_authority_events,
        critic_spec=selected,
    )
    _require_historical_coverage(
        retirement=retired.retirement,
        evaluation_outcome_sha256s=outcome_sha256s,
        promotion_authority_event_sha256s=promotion_sha256s,
    )
    return AcceptanceManifestReveal.create(
        critic_spec=selected,
        case_manifest=selected_case_manifest,
        scoring_policy=selected_scoring_policy,
        salt=selected_salt,
        retirement_authority_event_sha256=retired.authority_event.event.content_sha256,
        evaluation_outcome_sha256s=outcome_sha256s,
        promotion_sha256s=promotion_sha256s,
    )


def reveal_retired_acceptance_manifest(
    *,
    ledger: AuthorityLedger,
    reveal: AcceptanceManifestReveal,
    retirement_authority: StoredAuthorityEvent,
    evaluation_outcomes: tuple[BasisReference, ...],
    promotion_authority_events: tuple[StoredAuthorityEvent, ...],
    human_approval: BasisReference,
    event_id: str,
    kernel_sha256: str,
) -> StoredAcceptanceManifestReveal:
    """Persist and authorize one independently reloadable retirement-bound reveal."""
    selected_reveal = AcceptanceManifestReveal.model_validate(reveal.model_dump(mode="python"))
    expected = prepare_acceptance_manifest_reveal(
        ledger=ledger,
        critic_spec=selected_reveal.critic_spec,
        retirement_authority=retirement_authority,
        case_manifest=selected_reveal.case_manifest,
        scoring_policy=selected_reveal.scoring_policy,
        salt=selected_reveal.salt,
        evaluation_outcomes=evaluation_outcomes,
        promotion_authority_events=promotion_authority_events,
    )
    if selected_reveal != expected:
        raise AuthorityLedgerIntegrityError("acceptance manifest reveal does not match exact retirement evidence")
    retired = _load_exact_retirement(
        ledger=ledger,
        stored=retirement_authority,
    )
    if retired.authority_event.event.kernel_sha256 != kernel_sha256:
        raise AuthorityLedgerIntegrityError("acceptance reveal kernel does not match retirement authority")
    subject_id = _reveal_subject_id(selected_reveal.critic_spec)
    approval = _resolve_human_approval(
        ledger=ledger,
        reference=human_approval,
        action=AuthorityAction.REVEAL_ACCEPTANCE_MANIFEST,
        subject_id=subject_id,
        subject_sha256=selected_reveal.content_sha256,
        mismatch_message="human approval does not match the exact acceptance manifest reveal",
    )
    critic_basis = _observe_critic_spec(
        ledger=ledger,
        critic_spec=selected_reveal.critic_spec,
        event_id=event_id,
        operation_id="reveal-acceptance-manifest",
    )
    retirement_event_basis = _observe_authority_event_basis(
        ledger=ledger,
        stored=retired.authority_event,
        artifact_id=f"acceptance-reveal.{event_id}.retirement-authority",
        operation_id="reveal-acceptance-manifest",
        invocation_id=event_id,
    )
    outcome_bases, _ = _resolve_evaluation_outcomes(
        ledger=ledger,
        references=evaluation_outcomes,
    )
    promotions, _ = _resolve_promotion_authorities(
        ledger=ledger,
        events=promotion_authority_events,
        critic_spec=selected_reveal.critic_spec,
    )
    promotion_bases = tuple(
        _observe_authority_event_basis(
            ledger=ledger,
            stored=promotion,
            artifact_id=f"acceptance-reveal.{event_id}.promotion.{index}",
            operation_id="reveal-acceptance-manifest",
            invocation_id=event_id,
        )
        for index, promotion in enumerate(promotions)
    )
    reveal_basis = _observe_governance_evidence(
        ledger=ledger,
        artifact_id=f"acceptance-reveal.{event_id}",
        model=selected_reveal,
        operation_id="reveal-acceptance-manifest",
        invocation_id=event_id,
    )
    event = AuthorityEvent(
        event_id=event_id,
        principal=approval.principal,
        action=AuthorityAction.REVEAL_ACCEPTANCE_MANIFEST,
        decision=AuthorityDecision.GRANTED,
        subject_id=subject_id,
        subject_sha256=selected_reveal.content_sha256,
        basis=tuple(
            [
                human_approval,
                critic_basis.reference,
                retirement_event_basis.reference,
                retired.evidence.reference,
                reveal_basis.reference,
                *(basis.reference for basis in outcome_bases),
                *(basis.reference for basis in promotion_bases),
            ]
        ),
        kernel_sha256=kernel_sha256,
        critic_generation_sha256=selected_reveal.critic_spec.content_sha256,
        reasons=("human revealed exact retired acceptance manifest and complete historical coverage",),
        revalidation_triggers=("historical_acceptance_replay_due",),
    )
    authority = ledger.issue_authority_event(event)
    return StoredAcceptanceManifestReveal(
        reveal=selected_reveal,
        evidence=reveal_basis,
        retirement=retired.retirement,
        authority_event=authority,
    )


def load_acceptance_manifest_reveal(
    *,
    ledger: AuthorityLedger,
    event_id: str,
    content_sha256: str,
) -> StoredAcceptanceManifestReveal:
    """Reload reveal bytes and verify their retirement, history, and human authority."""
    authority = ledger.resolve_authority_event(
        event_id=event_id,
        content_sha256=content_sha256,
    )
    event = authority.event
    if (
        event.action is not AuthorityAction.REVEAL_ACCEPTANCE_MANIFEST
        or event.decision is not AuthorityDecision.GRANTED
    ):
        raise AuthorityLedgerIntegrityError("acceptance reveal requires exact granted reveal authority")
    reveal_basis, reveal = _find_evidence_model(
        ledger=ledger,
        references=event.basis,
        model_type=AcceptanceManifestReveal,
        label="acceptance manifest reveal",
    )
    subject_id = _reveal_subject_id(reveal.critic_spec)
    if (
        event.subject_id != subject_id
        or event.subject_sha256 != reveal.content_sha256
        or event.critic_generation_sha256 != reveal.critic_spec.content_sha256
    ):
        raise AuthorityLedgerIntegrityError("reveal authority does not match the exact acceptance critic subject")
    _require_event_human_authority(
        ledger=ledger,
        event=event,
    )
    retirement_event = ledger.resolve_authority_event_by_content(reveal.retirement_authority_event_sha256)
    retired = _load_exact_retirement(
        ledger=ledger,
        stored=retirement_event,
    )
    if not _event_has_exact_authority_basis(
        ledger=ledger,
        event=event,
        expected=retired.authority_event.event,
    ):
        raise AuthorityLedgerIntegrityError("reveal authority is missing its exact retirement authority basis")
    _require_retirement_for_critic(retired.retirement, reveal.critic_spec)
    outcome_bases, outcome_sha256s = _event_evaluation_outcomes(
        ledger=ledger,
        event=event,
    )
    del outcome_bases
    promotion_events, promotion_sha256s = _event_promotion_authorities(
        ledger=ledger,
        event=event,
        critic_spec=reveal.critic_spec,
    )
    del promotion_events
    _require_historical_coverage(
        retirement=retired.retirement,
        evaluation_outcome_sha256s=outcome_sha256s,
        promotion_authority_event_sha256s=promotion_sha256s,
    )
    if (
        reveal.evaluation_outcome_sha256s != outcome_sha256s
        or reveal.promotion_sha256s != promotion_sha256s
        or reveal_basis.reference not in event.basis
        or retired.evidence.reference not in event.basis
    ):
        raise AuthorityLedgerIntegrityError("reveal authority is missing exact retirement-bound historical coverage")
    return StoredAcceptanceManifestReveal(
        reveal=reveal,
        evidence=reveal_basis,
        retirement=retired.retirement,
        authority_event=authority,
    )


def assert_acceptance_audit_closed(
    *,
    ledger: AuthorityLedger,
    retirement_authority: StoredAuthorityEvent,
    reveal_authority: StoredAuthorityEvent | None,
) -> AcceptanceAuditClosure:
    """Fail closed unless one exact retired acceptance generation has been revealed."""
    retirement = _load_exact_retirement(
        ledger=ledger,
        stored=retirement_authority,
    )
    if reveal_authority is None:
        raise AuthorityLedgerIntegrityError(
            "retired acceptance generation is unrevealed and its audit lifecycle is not closed"
        )
    reveal = load_acceptance_manifest_reveal(
        ledger=ledger,
        event_id=reveal_authority.event.event_id,
        content_sha256=reveal_authority.event.content_sha256,
    )
    if (
        reveal.reveal.retirement_authority_event_sha256 != retirement.authority_event.event.content_sha256
        or reveal.retirement != retirement.retirement
    ):
        raise AuthorityLedgerIntegrityError(
            "acceptance audit closure reveal does not match the exact retirement authority"
        )
    return AcceptanceAuditClosure(
        retirement=retirement,
        reveal=reveal,
    )
