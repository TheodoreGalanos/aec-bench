# ABOUTME: Maintains append-only assurance state for stable Hx/px motif subjects.
# ABOUTME: Keeps selection-time assurance and fails dispatch or promotion closed when that state drifts.

from __future__ import annotations

from enum import StrEnum
from typing import Literal, Self

from pydantic import field_validator, model_validator

from aec_bench.contracts.authority import (
    AuthorityAction,
    AuthorityDecision,
    BasisKind,
    MotifPromotionQualification,
)
from aec_bench.contracts.content_address import ContentAddressedModel
from aec_bench.contracts.evaluation_refs import CriticRef
from aec_bench.contracts.harness_kernel import (
    FrozenStrictModel,
    KernelRef,
    canonical_json_sha256,
    validate_sha256,
)
from aec_bench.contracts.validators import NonEmptyStr
from aec_bench.experimentation.governance.authority_ledger import AuthorityLedger, AuthorityLedgerError
from aec_bench.experimentation.governance.motifs import (
    HarnessProgramMotif,
    MotifPromotionDecision,
    MotifPromotionPolicy,
    MotifSelectionDecision,
    MotifSelectionOutcome,
    MotifSelectionRequest,
    MotifStatus,
    apply_motif_promotion,
    decide_motif_promotion,
)
from aec_bench.experimentation.governance.motifs.promotion import apply_authorized_motif_promotion


class MotifAssuranceState(StrEnum):
    """Effective assurance states kept separately from immutable motif evidence records."""

    ACTIVE = "active"
    STALE = "stale"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    SUPERSEDED = "superseded"
    RETIRED = "retired"


class MotifAssuranceBoundary(StrEnum):
    """Consequential runtime boundaries that must recheck the selected assurance snapshot."""

    DISPATCH = "dispatch"
    PROMOTION = "promotion"


class MotifAssuranceDriftError(ValueError):
    """Raised when a selection-time assurance pin is no longer current."""

    def __init__(self, boundary: MotifAssuranceBoundary, reason: str) -> None:
        self.boundary = boundary
        self.reason = reason
        super().__init__(f"{boundary.value} blocked: motif assurance {reason}")


class MotifAssuranceAuthorityError(ValueError):
    """Raised when a lifecycle transition lacks exact scoped authority."""


class MotifLifecycleEvent(ContentAddressedModel):
    """One authorized append-only state transition for a stable motif subject."""

    schema_version: Literal["aecbench.motif-lifecycle-event.v1"] = "aecbench.motif-lifecycle-event.v1"
    event_id: NonEmptyStr
    motif_subject_sha256: str
    state: MotifAssuranceState
    cause: NonEmptyStr
    parent_event_sha256: str | None = None
    authority_event_sha256: str
    revalidation_basis_sha256: str | None = None
    kernel_ref: KernelRef
    kernel_abi_sha256: str
    critic: CriticRef | None = None
    model_generation_sha256: str | None = None
    tool_generation_sha256: str | None = None
    applicability_sha256: str
    revalidation_triggers: tuple[NonEmptyStr, ...] = ()

    @field_validator(
        "motif_subject_sha256",
        "parent_event_sha256",
        "authority_event_sha256",
        "revalidation_basis_sha256",
        "kernel_abi_sha256",
        "model_generation_sha256",
        "tool_generation_sha256",
        "applicability_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str | None) -> str | None:
        return None if value is None else validate_sha256(value)

    @field_validator("revalidation_triggers")
    @classmethod
    def canonicalize_triggers(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("motif revalidation triggers must be unique")
        return tuple(sorted(value))


class MotifAssuranceEntry(FrozenStrictModel):
    """Latest effective assurance state for one stable motif subject."""

    motif_subject_sha256: str
    state: MotifAssuranceState
    head_event_sha256: str
    authority_event_sha256: str
    kernel_ref: KernelRef
    kernel_abi_sha256: str
    critic: CriticRef | None = None
    model_generation_sha256: str | None = None
    tool_generation_sha256: str | None = None
    applicability_sha256: str
    revalidation_required: bool
    eligible: bool

    @field_validator(
        "motif_subject_sha256",
        "head_event_sha256",
        "authority_event_sha256",
        "kernel_abi_sha256",
        "model_generation_sha256",
        "tool_generation_sha256",
        "applicability_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str | None) -> str | None:
        return None if value is None else validate_sha256(value)

    @model_validator(mode="after")
    def validate_effective_flags(self) -> Self:
        if self.eligible is not (self.state is MotifAssuranceState.ACTIVE):
            raise ValueError("motif assurance eligibility must equal the active state")
        expected_revalidation = self.state in {
            MotifAssuranceState.STALE,
            MotifAssuranceState.SUSPENDED,
        }
        if self.revalidation_required is not expected_revalidation:
            raise ValueError("motif assurance revalidation flag does not match its state")
        return self


class MotifAssuranceLedger(ContentAddressedModel):
    """Immutable append-only event chain with one independently linked head per motif subject."""

    schema_version: Literal["aecbench.motif-assurance-ledger.v1"] = "aecbench.motif-assurance-ledger.v1"
    events: tuple[MotifLifecycleEvent, ...] = ()

    @model_validator(mode="after")
    def validate_event_chains(self) -> Self:
        event_ids: set[str] = set()
        event_hashes: set[str] = set()
        heads: dict[str, MotifLifecycleEvent] = {}
        for event in self.events:
            if event.event_id in event_ids or event.content_sha256 in event_hashes:
                raise ValueError("motif lifecycle events must be unique by id and content")
            event_ids.add(event.event_id)
            event_hashes.add(event.content_sha256)
            prior = heads.get(event.motif_subject_sha256)
            if prior is None:
                if event.parent_event_sha256 is not None:
                    raise ValueError("first motif lifecycle event cannot name a parent")
                if event.state is not MotifAssuranceState.ACTIVE:
                    raise ValueError("first motif lifecycle event must activate the subject")
            else:
                if event.parent_event_sha256 != prior.content_sha256:
                    raise ValueError("motif lifecycle event must extend the current subject head")
                _validate_transition(prior, event)
            heads[event.motif_subject_sha256] = event
        return self

    @classmethod
    def create(cls) -> MotifAssuranceLedger:
        """Create an empty append-only assurance ledger."""
        return cls()

    def append(self, event: MotifLifecycleEvent) -> MotifAssuranceLedger:
        """Return a new ledger whose final event extends the relevant current subject head."""
        normalized = MotifLifecycleEvent.model_validate(event.model_dump(mode="python"))
        return MotifAssuranceLedger(events=(*self.events, normalized))


class MotifAssuranceSnapshot(ContentAddressedModel):
    """Content-addressed effective-state projection derived from one exact assurance ledger."""

    schema_version: Literal["aecbench.motif-assurance-snapshot.v1"] = "aecbench.motif-assurance-snapshot.v1"
    source_ledger_sha256: str
    entries: tuple[MotifAssuranceEntry, ...] = ()

    @field_validator("source_ledger_sha256")
    @classmethod
    def validate_ledger_hash(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("entries")
    @classmethod
    def canonicalize_entries(
        cls,
        value: tuple[MotifAssuranceEntry, ...],
    ) -> tuple[MotifAssuranceEntry, ...]:
        subjects = tuple(entry.motif_subject_sha256 for entry in value)
        if len(subjects) != len(set(subjects)):
            raise ValueError("motif assurance snapshot subjects must be unique")
        return tuple(sorted(value, key=lambda entry: entry.motif_subject_sha256))

    def require(self, motif_subject_sha256: str) -> MotifAssuranceEntry:
        """Resolve one subject or fail closed when the snapshot has no assurance state for it."""
        validate_sha256(motif_subject_sha256)
        entry = next(
            (candidate for candidate in self.entries if candidate.motif_subject_sha256 == motif_subject_sha256),
            None,
        )
        if entry is None:
            raise ValueError("motif subject is absent from the assurance snapshot")
        return entry


class MotifAssurancePin(ContentAddressedModel):
    """Frozen selection record binding one motif to the exact active assurance snapshot."""

    schema_version: Literal["aecbench.motif-assurance-pin.v1"] = "aecbench.motif-assurance-pin.v1"
    selection_id: NonEmptyStr
    selected_motif_sha256: str
    motif_subject_sha256: str
    assurance_snapshot_sha256: str
    assurance_head_event_sha256: str

    @field_validator(
        "selected_motif_sha256",
        "motif_subject_sha256",
        "assurance_snapshot_sha256",
        "assurance_head_event_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @classmethod
    def create(
        cls,
        *,
        selection_id: str,
        selected_motif_sha256: str,
        motif_subject_sha256: str,
        snapshot: MotifAssuranceSnapshot,
    ) -> MotifAssurancePin:
        """Pin one selected motif only while its effective assurance state is active."""
        normalized = MotifAssuranceSnapshot.model_validate(snapshot.model_dump(mode="python"))
        entry = normalized.require(motif_subject_sha256)
        if not entry.eligible:
            raise ValueError("motif assurance pin requires an active eligible subject")
        return cls(
            selection_id=selection_id,
            selected_motif_sha256=selected_motif_sha256,
            motif_subject_sha256=motif_subject_sha256,
            assurance_snapshot_sha256=normalized.content_sha256,
            assurance_head_event_sha256=entry.head_event_sha256,
        )


class AssuredMotifSelectionRecord(ContentAddressedModel):
    """Frozen selection record containing the exact decision and its active assurance pin."""

    schema_version: Literal["aecbench.assured-motif-selection.v1"] = "aecbench.assured-motif-selection.v1"
    selection_request: MotifSelectionRequest
    selection_decision: MotifSelectionDecision
    selected_motif_sha256: str
    motif_subject_sha256: str
    assurance_authority_event_sha256: str
    assurance_pin: MotifAssurancePin

    @field_validator(
        "selected_motif_sha256",
        "motif_subject_sha256",
        "assurance_authority_event_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_selection_binding(self) -> Self:
        request = self.selection_request
        decision = self.selection_decision
        if decision.request_sha256 != request.request_sha256 or (
            decision.archive_sha256,
            decision.archive_frozen,
            decision.kernel_abi_sha256,
            decision.applicability,
            decision.target_review_lineage_ids,
            decision.eligible_statuses,
            decision.selection_split,
        ) != (
            request.archive_sha256,
            request.archive_frozen,
            request.kernel_abi_sha256,
            request.applicability,
            request.target_review_lineage_ids,
            request.eligible_statuses,
            request.selection_split,
        ):
            raise ValueError("assured selection decision does not bind its exact request")
        if (
            decision.outcome is not MotifSelectionOutcome.SELECTED
            or decision.selected_motif_sha256 != self.selected_motif_sha256
        ):
            raise ValueError("assured selection requires the exact selected motif")
        pin = self.assurance_pin
        if (
            pin.selection_id != decision.decision_sha256
            or pin.selected_motif_sha256 != self.selected_motif_sha256
            or pin.motif_subject_sha256 != self.motif_subject_sha256
        ):
            raise ValueError("assured selection pin does not bind its exact decision and motif subject")
        return self

    @classmethod
    def create(
        cls,
        *,
        selection_request: MotifSelectionRequest,
        selection_decision: MotifSelectionDecision,
        selected_motif: HarnessProgramMotif,
        snapshot: MotifAssuranceSnapshot,
    ) -> AssuredMotifSelectionRecord:
        """Bind a selected legacy motif decision to one exact active assurance snapshot."""
        request = MotifSelectionRequest.model_validate(selection_request.model_dump(mode="python"))
        decision = MotifSelectionDecision.model_validate(selection_decision.model_dump(mode="python"))
        motif = HarnessProgramMotif.model_validate(selected_motif.model_dump(mode="python"))
        current = MotifAssuranceSnapshot.model_validate(snapshot.model_dump(mode="python"))
        expected_decision = MotifSelectionDecision.create(
            request=request,
            selected_motif=motif,
        )
        if decision != expected_decision:
            raise ValueError("assured selection decision does not bind the supplied selected motif")
        subject_sha256 = motif_subject_sha256(motif)
        entry = current.require(subject_sha256)
        if not entry.eligible:
            raise ValueError("assured selection requires an active eligible motif subject")
        pin = MotifAssurancePin.create(
            selection_id=decision.decision_sha256,
            selected_motif_sha256=motif.motif_sha256,
            motif_subject_sha256=subject_sha256,
            snapshot=current,
        )
        return cls(
            selection_request=request,
            selection_decision=decision,
            selected_motif_sha256=motif.motif_sha256,
            motif_subject_sha256=subject_sha256,
            assurance_authority_event_sha256=entry.authority_event_sha256,
            assurance_pin=pin,
        )


def motif_subject_sha256(motif: HarnessProgramMotif) -> str:
    """Hash only stable K/Hx/px/applicability/structure fields, excluding status and evidence."""
    normalized = HarnessProgramMotif.model_validate(motif.model_dump(mode="python"))
    return canonical_json_sha256(
        {
            "schema_version": "aecbench.motif-subject.v1",
            "kernel_abi_sha256": normalized.kernel_abi_sha256,
            "hx_template_sha256": normalized.hx_template.template_sha256,
            "px_template_sha256": normalized.px_template.template_sha256,
            "applicability": normalized.applicability.model_dump(mode="json"),
            "descriptor": normalized.descriptor.model_dump(mode="json"),
        }
    )


def derive_motif_assurance_snapshot(
    ledger: MotifAssuranceLedger,
) -> MotifAssuranceSnapshot:
    """Project the final authorized event for each subject into a deterministic snapshot."""
    normalized = MotifAssuranceLedger.model_validate(ledger.model_dump(mode="python"))
    heads: dict[str, MotifLifecycleEvent] = {}
    for event in normalized.events:
        heads[event.motif_subject_sha256] = event
    entries = tuple(
        MotifAssuranceEntry(
            motif_subject_sha256=subject_sha256,
            state=event.state,
            head_event_sha256=event.content_sha256,
            authority_event_sha256=event.authority_event_sha256,
            kernel_ref=event.kernel_ref,
            kernel_abi_sha256=event.kernel_abi_sha256,
            critic=event.critic,
            model_generation_sha256=event.model_generation_sha256,
            tool_generation_sha256=event.tool_generation_sha256,
            applicability_sha256=event.applicability_sha256,
            revalidation_required=event.state
            in {
                MotifAssuranceState.STALE,
                MotifAssuranceState.SUSPENDED,
            },
            eligible=event.state is MotifAssuranceState.ACTIVE,
        )
        for subject_sha256, event in sorted(heads.items())
    )
    return MotifAssuranceSnapshot(
        source_ledger_sha256=normalized.content_sha256,
        entries=entries,
    )


def assert_motif_assurance_current(
    pin: MotifAssurancePin,
    current_snapshot: MotifAssuranceSnapshot,
    *,
    boundary: MotifAssuranceBoundary,
) -> None:
    """Fail a dispatch or promotion barrier unless the exact selected snapshot remains active."""
    selected = MotifAssurancePin.model_validate(pin.model_dump(mode="python"))
    current = MotifAssuranceSnapshot.model_validate(current_snapshot.model_dump(mode="python"))
    if current.content_sha256 != selected.assurance_snapshot_sha256:
        raise MotifAssuranceDriftError(boundary, "snapshot drift")
    try:
        entry = current.require(selected.motif_subject_sha256)
    except ValueError as error:
        raise MotifAssuranceDriftError(boundary, "subject missing") from error
    if not entry.eligible:
        raise MotifAssuranceDriftError(boundary, f"subject state is {entry.state.value}")
    if entry.head_event_sha256 != selected.assurance_head_event_sha256:
        raise MotifAssuranceDriftError(boundary, "subject head drift")


def assert_assured_motif_selection_current(
    record: AssuredMotifSelectionRecord,
    selected_motif: HarnessProgramMotif,
    current_snapshot: MotifAssuranceSnapshot,
    *,
    authority_ledger: AuthorityLedger,
    boundary: MotifAssuranceBoundary,
) -> None:
    """Recheck selection, effective assurance, and durable authority at a consequential boundary."""
    selected = AssuredMotifSelectionRecord.model_validate(record.model_dump(mode="python"))
    motif = HarnessProgramMotif.model_validate(selected_motif.model_dump(mode="python"))
    if (
        motif.motif_sha256 != selected.selected_motif_sha256
        or motif_subject_sha256(motif) != selected.motif_subject_sha256
    ):
        raise ValueError("assured selection selected motif does not match the supplied motif")
    expected_decision = MotifSelectionDecision.create(
        request=selected.selection_request,
        selected_motif=motif,
    )
    if selected.selection_decision != expected_decision:
        raise ValueError("assured selection decision does not bind the supplied selected motif")
    current = MotifAssuranceSnapshot.model_validate(current_snapshot.model_dump(mode="python"))
    assert_motif_assurance_current(
        selected.assurance_pin,
        current,
        boundary=boundary,
    )
    entry = current.require(selected.motif_subject_sha256)
    if entry.authority_event_sha256 != selected.assurance_authority_event_sha256:
        raise MotifAssuranceAuthorityError("stale authority basis: assurance authority changed")
    try:
        authority = authority_ledger.resolve_authority_event_by_content(selected.assurance_authority_event_sha256).event
    except AuthorityLedgerError as error:
        raise MotifAssuranceAuthorityError(
            "stale authority basis: exact assurance authority is not durably resolvable"
        ) from error
    if (
        authority.decision is not AuthorityDecision.GRANTED
        or authority.action
        not in {
            AuthorityAction.MOTIF_PROMOTION,
            AuthorityAction.MOTIF_STATE_CHANGE,
        }
        or authority.subject_sha256 != selected.motif_subject_sha256
        or authority.kernel_ref != entry.kernel_ref
        or (authority.critic is not None and authority.critic != entry.critic)
    ):
        raise MotifAssuranceAuthorityError(
            "stale authority basis: exact assurance authority no longer scopes the selected subject"
        )


def apply_governed_motif_promotion(
    motif: HarnessProgramMotif,
    decision: MotifPromotionDecision,
    policy: MotifPromotionPolicy,
    *,
    authority_ledger: AuthorityLedger,
    authority_event_sha256: str,
    assured_selection: AssuredMotifSelectionRecord | None = None,
    selected_motif: HarnessProgramMotif | None = None,
    current_snapshot: MotifAssuranceSnapshot | None = None,
) -> HarnessProgramMotif:
    """Apply one protected edge only from exact authority and an already-assured selection."""

    source = HarnessProgramMotif.model_validate(motif.model_dump(mode="python"))
    selected_decision = MotifPromotionDecision.model_validate(decision.model_dump(mode="python"))
    selected_policy = MotifPromotionPolicy.model_validate(policy.model_dump(mode="python"))
    expected = decide_motif_promotion(
        source,
        selected_decision.target_status,
        selected_policy,
    )
    if selected_decision != expected or not selected_decision.accepted:
        raise ValueError("governed motif promotion requires the exact accepted evidence decision")
    if selected_decision.target_status is MotifStatus.REUSABLE:
        return _apply_reusable_motif_promotion(
            source=source,
            decision=selected_decision,
            policy=selected_policy,
            authority_ledger=authority_ledger,
            authority_event_sha256=authority_event_sha256,
            assured_selection=assured_selection,
            selected_motif=selected_motif,
            current_snapshot=current_snapshot,
        )
    if selected_decision.target_status is not MotifStatus.TRANSFER_VALIDATED:
        return apply_motif_promotion(
            source,
            selected_decision,
            selected_policy,
        )
    return _apply_transfer_validated_motif_promotion(
        source=source,
        decision=selected_decision,
        policy=selected_policy,
        authority_ledger=authority_ledger,
        authority_event_sha256=authority_event_sha256,
        assured_selection=assured_selection,
        selected_motif=selected_motif,
        current_snapshot=current_snapshot,
    )


def _apply_reusable_motif_promotion(
    *,
    source: HarnessProgramMotif,
    decision: MotifPromotionDecision,
    policy: MotifPromotionPolicy,
    authority_ledger: AuthorityLedger,
    authority_event_sha256: str,
    assured_selection: AssuredMotifSelectionRecord | None,
    selected_motif: HarnessProgramMotif | None,
    current_snapshot: MotifAssuranceSnapshot | None,
) -> HarnessProgramMotif:
    if assured_selection is not None or selected_motif is not None or current_snapshot is not None:
        raise MotifAssuranceAuthorityError("first reusable promotion must not depend on prior motif assurance")
    try:
        authority = authority_ledger.resolve_authority_event_by_content(authority_event_sha256).event
    except AuthorityLedgerError as error:
        raise MotifAssuranceAuthorityError("reusable promotion authority is not durably resolvable") from error
    qualification_refs = tuple(
        reference for reference in authority.basis if reference.kind is BasisKind.MOTIF_QUALIFICATION
    )
    if len(qualification_refs) != 1:
        raise MotifAssuranceAuthorityError("reusable promotion requires one exact motif qualification basis")
    try:
        _, qualification = authority_ledger.resolve_model_basis(
            qualification_refs[0],
            MotifPromotionQualification,
        )
    except AuthorityLedgerError as error:
        raise MotifAssuranceAuthorityError("reusable promotion qualification is not durably resolvable") from error
    subject_sha256 = motif_subject_sha256(source)
    if (
        authority.decision is not AuthorityDecision.GRANTED
        or authority.action is not AuthorityAction.MOTIF_PROMOTION
        or authority.subject_sha256 != subject_sha256
        or authority.kernel_ref != qualification.kernel_ref
        or authority.critic != qualification.critic
        or qualification.provisional_motif_sha256 != source.motif_sha256
        or qualification.motif_subject_sha256 != subject_sha256
        or qualification.kernel_abi_sha256 != source.kernel_abi_sha256
    ):
        raise MotifAssuranceAuthorityError(
            "reusable promotion authority does not bind the exact qualified provisional motif"
        )
    return apply_authorized_motif_promotion(
        source,
        decision,
        policy,
    )


def _apply_transfer_validated_motif_promotion(
    *,
    source: HarnessProgramMotif,
    decision: MotifPromotionDecision,
    policy: MotifPromotionPolicy,
    authority_ledger: AuthorityLedger,
    authority_event_sha256: str,
    assured_selection: AssuredMotifSelectionRecord | None,
    selected_motif: HarnessProgramMotif | None,
    current_snapshot: MotifAssuranceSnapshot | None,
) -> HarnessProgramMotif:
    if assured_selection is None or selected_motif is None or current_snapshot is None:
        raise MotifAssuranceAuthorityError(
            "transfer-validated promotion requires the exact assured selection and current snapshot"
        )

    selected = HarnessProgramMotif.model_validate(selected_motif.model_dump(mode="python"))
    if selected.status is not MotifStatus.REUSABLE:
        raise MotifAssuranceAuthorityError("transfer-validated promotion requires a selected reusable motif")
    subject_sha256 = motif_subject_sha256(source)
    if motif_subject_sha256(selected) != subject_sha256:
        raise MotifAssuranceAuthorityError(
            "transfer-validated evidence and selected motif bind different stable subjects"
        )
    snapshot = MotifAssuranceSnapshot.model_validate(current_snapshot.model_dump(mode="python"))
    assert_assured_motif_selection_current(
        assured_selection,
        selected,
        snapshot,
        authority_ledger=authority_ledger,
        boundary=MotifAssuranceBoundary.PROMOTION,
    )
    try:
        authority = authority_ledger.resolve_authority_event_by_content(authority_event_sha256).event
    except AuthorityLedgerError as error:
        raise MotifAssuranceAuthorityError(
            "transfer-validated promotion authority is not durably resolvable"
        ) from error
    assurance_entry = snapshot.require(subject_sha256)
    if (
        authority.decision is not AuthorityDecision.GRANTED
        or authority.action is not AuthorityAction.MOTIF_STATE_CHANGE
        or authority.subject_sha256 != subject_sha256
        or authority.kernel_ref != assurance_entry.kernel_ref
        or assurance_entry.kernel_abi_sha256 != source.kernel_abi_sha256
        or authority.critic != assurance_entry.critic
    ):
        raise MotifAssuranceAuthorityError(
            "transfer-validated promotion requires exact granted motif_state_change "
            "authority for the assured subject, kernel, and regime critic"
        )
    return apply_authorized_motif_promotion(
        source,
        decision,
        policy,
    )


def append_authorized_motif_event(
    ledger: MotifAssuranceLedger,
    event: MotifLifecycleEvent,
    *,
    authority_ledger: AuthorityLedger,
) -> MotifAssuranceLedger:
    """Append one motif transition only after replaying its exact scoped authority event."""
    selected_ledger = MotifAssuranceLedger.model_validate(ledger.model_dump(mode="python"))
    selected_event = MotifLifecycleEvent.model_validate(event.model_dump(mode="python"))
    authority = authority_ledger.resolve_authority_event_by_content(selected_event.authority_event_sha256).event
    has_subject = any(
        prior.motif_subject_sha256 == selected_event.motif_subject_sha256 for prior in selected_ledger.events
    )
    expected_action = AuthorityAction.MOTIF_STATE_CHANGE if has_subject else AuthorityAction.MOTIF_PROMOTION
    if authority.decision is not AuthorityDecision.GRANTED or authority.action is not expected_action:
        raise MotifAssuranceAuthorityError(
            f"motif lifecycle transition requires granted {expected_action.value} authority"
        )
    if authority.subject_sha256 != selected_event.motif_subject_sha256:
        raise MotifAssuranceAuthorityError("motif lifecycle authority subject does not match the stable motif subject")
    if authority.kernel_ref != selected_event.kernel_ref:
        raise MotifAssuranceAuthorityError("motif lifecycle authority and event bind different kernels")
    if authority.critic is not None and authority.critic != selected_event.critic:
        raise MotifAssuranceAuthorityError("motif lifecycle authority and event bind different regime critics")
    return selected_ledger.append(selected_event)


def _validate_transition(
    prior: MotifLifecycleEvent,
    event: MotifLifecycleEvent,
) -> None:
    allowed = {
        MotifAssuranceState.ACTIVE: {
            MotifAssuranceState.STALE,
            MotifAssuranceState.SUSPENDED,
            MotifAssuranceState.REVOKED,
            MotifAssuranceState.SUPERSEDED,
            MotifAssuranceState.RETIRED,
        },
        MotifAssuranceState.STALE: {
            MotifAssuranceState.ACTIVE,
            MotifAssuranceState.SUSPENDED,
            MotifAssuranceState.REVOKED,
            MotifAssuranceState.SUPERSEDED,
            MotifAssuranceState.RETIRED,
        },
        MotifAssuranceState.SUSPENDED: {
            MotifAssuranceState.ACTIVE,
            MotifAssuranceState.STALE,
            MotifAssuranceState.REVOKED,
            MotifAssuranceState.SUPERSEDED,
            MotifAssuranceState.RETIRED,
        },
        MotifAssuranceState.REVOKED: set(),
        MotifAssuranceState.SUPERSEDED: set(),
        MotifAssuranceState.RETIRED: set(),
    }[prior.state]
    if event.state not in allowed:
        raise ValueError(f"invalid motif assurance transition: {prior.state.value} -> {event.state.value}")
    if (
        event.state is MotifAssuranceState.ACTIVE
        and prior.state in {MotifAssuranceState.STALE, MotifAssuranceState.SUSPENDED}
        and event.revalidation_basis_sha256 is None
    ):
        raise ValueError("motif assurance reactivation requires a revalidation basis")
