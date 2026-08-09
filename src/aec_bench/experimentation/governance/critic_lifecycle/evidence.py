# ABOUTME: Resolves and persists exact authority, critic, outcome, and lifecycle evidence.
# ABOUTME: Centralizes governed authority, canonical-byte, historical-coverage, and ledger replay checks.


from __future__ import annotations

import json

from aec_bench.contracts.authority import (
    AuthorityAction,
    AuthorityDecision,
    AuthorityEvent,
    AuthorityPrincipal,
    AuthorityPrincipalKind,
    BasisKind,
    BasisReference,
    HumanAuthorityApproval,
    TaintLabel,
)
from aec_bench.contracts.evaluation_outcome import EvaluationOutcome
from aec_bench.contracts.evaluation_plane import (
    CriticRole,
    CriticSpec,
)
from aec_bench.contracts.harness_kernel import (
    ContentAddressedModel,
)
from aec_bench.experimentation.governance.authority_ledger import (
    AuthorityLedger,
    AuthorityLedgerIntegrityError,
    StoredAuthorityEvent,
    StoredBasis,
)

from .contracts import CriticGenerationRetirement, StoredCriticGenerationRetirement

_PROMOTION_ACTIONS = frozenset(
    {
        AuthorityAction.POLICY_PROMOTION,
        AuthorityAction.MOTIF_PROMOTION,
    }
)


def _critic_subject_id(critic_spec: CriticSpec) -> str:
    return f"{critic_spec.critic_id}@{critic_spec.version}"


def _reveal_subject_id(critic_spec: CriticSpec) -> str:
    return f"{_critic_subject_id(critic_spec)}#acceptance-manifest-reveal"


def _host_policy() -> AuthorityPrincipal:
    return AuthorityPrincipal(
        principal_id="host.critic-governance",
        kind=AuthorityPrincipalKind.HOST_POLICY,
    )


def _host_runtime() -> AuthorityPrincipal:
    return AuthorityPrincipal(
        principal_id="host.runtime",
        kind=AuthorityPrincipalKind.HOST_RUNTIME,
    )


def _require_acceptance_critic(critic_spec: CriticSpec) -> CriticSpec:
    selected = CriticSpec.model_validate(critic_spec.model_dump(mode="python"))
    if selected.role is not CriticRole.ACCEPTANCE or selected.acceptance_manifest_commitment is None:
        raise AuthorityLedgerIntegrityError("critic lifecycle operation requires an escrowed acceptance critic")
    return selected


def _resolve_human_approval(
    *,
    ledger: AuthorityLedger,
    reference: BasisReference,
    action: AuthorityAction,
    subject_id: str,
    subject_sha256: str,
    mismatch_message: str,
) -> HumanAuthorityApproval:
    stored, approval = ledger.resolve_model_basis(
        reference,
        HumanAuthorityApproval,
    )
    if (
        not approval.approved
        or approval.action is not action
        or approval.subject_id != subject_id
        or approval.subject_sha256 != subject_sha256
    ):
        raise AuthorityLedgerIntegrityError(mismatch_message)
    if (
        approval.principal.kind is not AuthorityPrincipalKind.HUMAN
        or stored.origin.producer != approval.principal
        or stored.origin.producer.kind is not AuthorityPrincipalKind.HUMAN
        or stored.origin.observed_by.kind
        not in {
            AuthorityPrincipalKind.HOST_POLICY,
            AuthorityPrincipalKind.HOST_RUNTIME,
        }
        or TaintLabel.HUMAN_AUTHORITY not in stored.origin.taint_labels
    ):
        raise AuthorityLedgerIntegrityError(
            "critic lifecycle transition requires matching host-observed human authority"
        )
    return approval


def _require_event_human_authority(
    *,
    ledger: AuthorityLedger,
    event: AuthorityEvent,
) -> None:
    for reference in event.basis:
        if reference.kind is not BasisKind.HUMAN_APPROVAL:
            continue
        try:
            approval = _resolve_human_approval(
                ledger=ledger,
                reference=reference,
                action=event.action,
                subject_id=event.subject_id,
                subject_sha256=event.subject_sha256,
                mismatch_message="authority event human approval does not match its exact subject",
            )
        except AuthorityLedgerIntegrityError:
            continue
        if approval.principal == event.principal:
            return
    raise AuthorityLedgerIntegrityError("critic lifecycle authority event lacks matching host-observed human authority")


def _observe_critic_spec(
    *,
    ledger: AuthorityLedger,
    critic_spec: CriticSpec,
    event_id: str,
    operation_id: str,
) -> StoredBasis:
    return ledger.observe_model_basis(
        kind=BasisKind.CRITIC_SPEC,
        artifact_id=f"critic-spec.{event_id}",
        model=critic_spec,
        producer=_host_policy(),
        producer_process_id="aecbench.critic-governance",
        observed_by=_host_runtime(),
        channel="critic-generation",
        operation_id=operation_id,
        invocation_id=event_id,
        operation_taint=(TaintLabel.RUNTIME_OBSERVED,),
    )


def _observe_authority_event_basis(
    *,
    ledger: AuthorityLedger,
    stored: StoredAuthorityEvent,
    artifact_id: str,
    operation_id: str,
    invocation_id: str,
) -> StoredBasis:
    resolved = _resolve_exact_event(ledger=ledger, stored=stored)
    taint = (
        (TaintLabel.HUMAN_AUTHORITY,)
        if resolved.event.principal.kind is AuthorityPrincipalKind.HUMAN
        else (TaintLabel.RUNTIME_OBSERVED,)
    )
    return ledger.observe_model_basis(
        kind=BasisKind.AUTHORITY_EVENT,
        artifact_id=artifact_id,
        model=resolved.event,
        producer=resolved.event.principal,
        producer_process_id="aecbench.authority-ledger",
        observed_by=_host_runtime(),
        channel="critic-lifecycle-authority",
        operation_id=operation_id,
        invocation_id=invocation_id,
        operation_taint=taint,
    )


def _observe_governance_evidence(
    *,
    ledger: AuthorityLedger,
    artifact_id: str,
    model: ContentAddressedModel,
    operation_id: str,
    invocation_id: str,
) -> StoredBasis:
    return ledger.observe_basis(
        kind=BasisKind.EVIDENCE,
        artifact_id=artifact_id,
        content=_canonical_model_bytes(model),
        producer=_host_policy(),
        producer_process_id="aecbench.critic-governance",
        observed_by=_host_runtime(),
        channel="critic-lifecycle-evidence",
        operation_id=operation_id,
        invocation_id=invocation_id,
        operation_taint=(TaintLabel.RUNTIME_OBSERVED,),
    )


def _resolve_exact_event(
    *,
    ledger: AuthorityLedger,
    stored: StoredAuthorityEvent,
) -> StoredAuthorityEvent:
    resolved = ledger.resolve_authority_event(
        event_id=stored.event.event_id,
        content_sha256=stored.event.content_sha256,
    )
    if resolved.event != stored.event:
        raise AuthorityLedgerIntegrityError("authority event object does not match its exact ledger record")
    return resolved


def _resolve_release_authority(
    *,
    ledger: AuthorityLedger,
    stored: StoredAuthorityEvent,
    critic_spec: CriticSpec,
) -> StoredAuthorityEvent:
    released = _resolve_exact_event(
        ledger=ledger,
        stored=stored,
    )
    event = released.event
    if (
        event.action is not AuthorityAction.RELEASE_CRITIC_GENERATION
        or event.decision is not AuthorityDecision.GRANTED
        or event.subject_id != _critic_subject_id(critic_spec)
        or event.subject_sha256 != critic_spec.content_sha256
        or event.critic_generation_sha256 != critic_spec.content_sha256
    ):
        raise AuthorityLedgerIntegrityError("release authority does not match the exact critic subject")
    _require_event_human_authority(
        ledger=ledger,
        event=event,
    )
    if not _event_has_exact_critic_basis(
        ledger=ledger,
        event=event,
        critic_spec=critic_spec,
    ):
        raise AuthorityLedgerIntegrityError("release authority is missing the exact critic spec basis")
    return released


def _resolve_evaluation_outcomes(
    *,
    ledger: AuthorityLedger,
    references: tuple[BasisReference, ...],
) -> tuple[tuple[StoredBasis, ...], tuple[str, ...]]:
    if len(references) != len(set(references)):
        raise AuthorityLedgerIntegrityError("historical evaluation outcome references must be unique")
    resolved: list[tuple[StoredBasis, EvaluationOutcome]] = []
    for reference in references:
        if reference.kind is not BasisKind.EVALUATION_OUTCOME:
            raise AuthorityLedgerIntegrityError(
                "historical evaluation coverage requires evaluation_outcome basis references"
            )
        resolved.append(
            ledger.resolve_model_basis(
                reference,
                EvaluationOutcome,
            )
        )
    resolved.sort(key=lambda item: item[1].content_sha256)
    digests = tuple(model.content_sha256 for _, model in resolved)
    if len(digests) != len(set(digests)):
        raise AuthorityLedgerIntegrityError("historical evaluation outcomes must be unique")
    return tuple(stored for stored, _ in resolved), digests


def _resolve_promotion_authorities(
    *,
    ledger: AuthorityLedger,
    events: tuple[StoredAuthorityEvent, ...],
    critic_spec: CriticSpec,
) -> tuple[tuple[StoredAuthorityEvent, ...], tuple[str, ...]]:
    resolved = tuple(
        sorted(
            (
                _resolve_exact_event(
                    ledger=ledger,
                    stored=event,
                )
                for event in events
            ),
            key=lambda item: item.event.content_sha256,
        )
    )
    digests = tuple(item.event.content_sha256 for item in resolved)
    if len(digests) != len(set(digests)):
        raise AuthorityLedgerIntegrityError("historical promotion authority events must be unique")
    for stored in resolved:
        event = stored.event
        if (
            event.action not in _PROMOTION_ACTIONS
            or event.decision is not AuthorityDecision.GRANTED
            or event.critic_generation_sha256 != critic_spec.content_sha256
        ):
            raise AuthorityLedgerIntegrityError(
                "historical promotion authority does not bind the exact critic generation"
            )
    return resolved, digests


def _require_historical_coverage(
    *,
    retirement: CriticGenerationRetirement,
    evaluation_outcome_sha256s: tuple[str, ...],
    promotion_authority_event_sha256s: tuple[str, ...],
) -> None:
    if (
        retirement.evaluation_outcome_sha256s != evaluation_outcome_sha256s
        or retirement.promotion_authority_event_sha256s != promotion_authority_event_sha256s
    ):
        raise AuthorityLedgerIntegrityError(
            "acceptance reveal historical coverage does not match the retirement record"
        )


def _require_retirement_for_critic(
    retirement: CriticGenerationRetirement,
    critic_spec: CriticSpec,
) -> None:
    if (
        retirement.retirement_id != f"{_critic_subject_id(critic_spec)}#retirement"
        or retirement.critic_id != critic_spec.critic_id
        or retirement.critic_version != critic_spec.version
        or retirement.critic_generation_sha256 != critic_spec.content_sha256
    ):
        raise AuthorityLedgerIntegrityError("critic retirement does not match the exact critic subject")


def _load_exact_retirement(
    *,
    ledger: AuthorityLedger,
    stored: StoredAuthorityEvent,
) -> StoredCriticGenerationRetirement:
    authority = _resolve_exact_event(
        ledger=ledger,
        stored=stored,
    )
    event = authority.event
    if event.action is not AuthorityAction.RETIRE_CRITIC_GENERATION or event.decision is not AuthorityDecision.GRANTED:
        raise AuthorityLedgerIntegrityError("acceptance reveal requires exact retirement authority")
    retirement_basis, retirement = _find_evidence_model(
        ledger=ledger,
        references=event.basis,
        model_type=CriticGenerationRetirement,
        label="critic generation retirement",
    )
    if (
        event.subject_id != retirement.retirement_id
        or event.subject_sha256 != retirement.content_sha256
        or event.critic_generation_sha256 != retirement.critic_generation_sha256
    ):
        raise AuthorityLedgerIntegrityError("retirement authority does not match the exact critic subject")
    _require_event_human_authority(
        ledger=ledger,
        event=event,
    )
    critic = _event_exact_critic(
        ledger=ledger,
        event=event,
        critic_generation_sha256=retirement.critic_generation_sha256,
    )
    _require_retirement_for_critic(retirement, critic)
    release = ledger.resolve_authority_event_by_content(retirement.release_authority_event_sha256)
    released = _resolve_release_authority(
        ledger=ledger,
        stored=release,
        critic_spec=critic,
    )
    if not _event_has_exact_authority_basis(
        ledger=ledger,
        event=event,
        expected=released.event,
    ):
        raise AuthorityLedgerIntegrityError("retirement authority is missing its exact release authority basis")
    _, outcome_sha256s = _event_evaluation_outcomes(
        ledger=ledger,
        event=event,
    )
    _, promotion_sha256s = _event_promotion_authorities(
        ledger=ledger,
        event=event,
        critic_spec=critic,
    )
    if (
        retirement.evaluation_outcome_sha256s != outcome_sha256s
        or retirement.promotion_authority_event_sha256s != promotion_sha256s
    ):
        raise AuthorityLedgerIntegrityError("retirement authority is missing exact declared historical coverage")
    return StoredCriticGenerationRetirement(
        retirement=retirement,
        evidence=retirement_basis,
        authority_event=authority,
    )


def _event_has_exact_critic_basis(
    *,
    ledger: AuthorityLedger,
    event: AuthorityEvent,
    critic_spec: CriticSpec,
) -> bool:
    return any(
        resolved == critic_spec
        for reference in event.basis
        if reference.kind is BasisKind.CRITIC_SPEC
        for _, resolved in (ledger.resolve_model_basis(reference, CriticSpec),)
    )


def _event_has_exact_authority_basis(
    *,
    ledger: AuthorityLedger,
    event: AuthorityEvent,
    expected: AuthorityEvent,
) -> bool:
    return any(
        resolved == expected
        for reference in event.basis
        if reference.kind is BasisKind.AUTHORITY_EVENT
        for _, resolved in (ledger.resolve_model_basis(reference, AuthorityEvent),)
    )


def _event_exact_critic(
    *,
    ledger: AuthorityLedger,
    event: AuthorityEvent,
    critic_generation_sha256: str,
) -> CriticSpec:
    critics = tuple(
        critic
        for reference in event.basis
        if reference.kind is BasisKind.CRITIC_SPEC
        for _, critic in (ledger.resolve_model_basis(reference, CriticSpec),)
        if critic.content_sha256 == critic_generation_sha256
    )
    if len(critics) != 1:
        raise AuthorityLedgerIntegrityError("critic lifecycle authority requires one exact critic spec basis")
    return critics[0]


def _event_evaluation_outcomes(
    *,
    ledger: AuthorityLedger,
    event: AuthorityEvent,
) -> tuple[tuple[StoredBasis, ...], tuple[str, ...]]:
    references = tuple(reference for reference in event.basis if reference.kind is BasisKind.EVALUATION_OUTCOME)
    return _resolve_evaluation_outcomes(
        ledger=ledger,
        references=references,
    )


def _event_promotion_authorities(
    *,
    ledger: AuthorityLedger,
    event: AuthorityEvent,
    critic_spec: CriticSpec,
) -> tuple[tuple[StoredAuthorityEvent, ...], tuple[str, ...]]:
    promotions: list[StoredAuthorityEvent] = []
    for reference in event.basis:
        if reference.kind is not BasisKind.AUTHORITY_EVENT:
            continue
        _, authority = ledger.resolve_model_basis(
            reference,
            AuthorityEvent,
        )
        if authority.action in _PROMOTION_ACTIONS:
            promotions.append(
                ledger.resolve_authority_event(
                    event_id=authority.event_id,
                    content_sha256=authority.content_sha256,
                )
            )
    return _resolve_promotion_authorities(
        ledger=ledger,
        events=tuple(promotions),
        critic_spec=critic_spec,
    )


def _find_evidence_model[ModelT: ContentAddressedModel](
    *,
    ledger: AuthorityLedger,
    references: tuple[BasisReference, ...],
    model_type: type[ModelT],
    label: str,
) -> tuple[StoredBasis, ModelT]:
    matches: list[tuple[StoredBasis, ModelT]] = []
    for reference in references:
        if reference.kind is not BasisKind.EVIDENCE:
            continue
        stored = ledger.resolve_basis(reference)
        encoded = stored.content_path.read_bytes()
        try:
            model = model_type.model_validate_json(encoded)
        except ValueError:
            continue
        if _canonical_model_bytes(model) != encoded:
            raise AuthorityLedgerIntegrityError(f"{label} evidence is not canonically serialized")
        matches.append((stored, model))
    if len(matches) != 1:
        raise AuthorityLedgerIntegrityError(f"{label} authority requires one exact durable evidence artifact")
    return matches[0]


def _load_evidence_reference[ModelT: ContentAddressedModel](
    *,
    ledger: AuthorityLedger,
    reference: BasisReference,
    model_type: type[ModelT],
    label: str,
) -> tuple[StoredBasis, ModelT]:
    if reference.kind is not BasisKind.EVIDENCE:
        raise AuthorityLedgerIntegrityError(f"{label} requires an evidence basis reference")
    stored = ledger.resolve_basis(reference)
    encoded = stored.content_path.read_bytes()
    try:
        model = model_type.model_validate_json(encoded)
    except ValueError as exc:
        raise AuthorityLedgerIntegrityError(f"{label} basis does not contain the required typed evidence") from exc
    if _canonical_model_bytes(model) != encoded:
        raise AuthorityLedgerIntegrityError(f"{label} evidence is not canonically serialized")
    return stored, model


def _canonical_model_bytes(model: ContentAddressedModel) -> bytes:
    return (
        json.dumps(
            model.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
