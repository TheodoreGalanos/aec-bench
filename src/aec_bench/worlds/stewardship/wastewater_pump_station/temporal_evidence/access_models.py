# ABOUTME: Defines strict search, fetch, result, receipt, and retrieval-state contracts.
# ABOUTME: Keeps actor-visible access evidence separate from host-private resolution data.

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import model_validator

from aec_bench.contracts.harness_kernel import canonical_json_sha256
from aec_bench.contracts.legacy_content_address import LegacyContentAddressedModel
from aec_bench.contracts.validators import FrozenStrictModel, NonEmptyStr
from aec_bench.worlds.stewardship.wastewater_pump_station.temporal_evidence.models import (
    RetrievalBudgetVector,
    TemporalEvidenceAuthorityClass,
    TemporalEvidenceSourceClass,
)


class TemporalEvidenceAccessKind(StrEnum):
    """Actor-selected documentary access operation."""

    SEARCH = "search"
    FETCH = "fetch"


class TemporalEvidenceAccessStatus(StrEnum):
    """Small public status set that does not reveal private frontier state."""

    OK = "OK"
    NO_ACCESSIBLE_RESULT = "NO_ACCESSIBLE_RESULT"
    RETRIEVAL_UNAVAILABLE = "RETRIEVAL_UNAVAILABLE"


class TemporalEvidencePrivateReason(StrEnum):
    """Host-private resolution reason retained for audit and falsification."""

    MATCH = "match"
    NO_MATCH = "no_match"
    FUTURE_EVIDENCE = "future_evidence"
    ACCESS_DENIED = "access_denied"
    BRANCH_MISMATCH = "branch_mismatch"
    SOURCE_UNAVAILABLE = "source_unavailable"
    UNISSUED_REFERENCE = "unissued_reference"
    BUDGET_EXHAUSTED = "budget_exhausted"
    INVALID_REQUEST = "invalid_request"


class TemporalAccessContext(LegacyContentAddressedModel):
    """Complete host-owned context for one deterministic search or fetch."""

    run_id: NonEmptyStr
    episode_id: NonEmptyStr
    world_instance_id: NonEmptyStr
    world_branch_id: NonEmptyStr
    world_state_id: NonEmptyStr
    world_commit_id: NonEmptyStr
    world_sequence: int
    world_time_seconds: int
    actor_id: NonEmptyStr
    actor_role: NonEmptyStr
    agent_tenure_id: NonEmptyStr
    session_id: NonEmptyStr
    base_view_id: NonEmptyStr
    prior_information_set_id: NonEmptyStr
    tool_contract_id: NonEmptyStr
    branch_ancestor_ids: tuple[NonEmptyStr, ...]

    @model_validator(mode="after")
    def validate_context(self) -> Self:
        if self.world_sequence < 0 or self.world_time_seconds < 0:
            raise ValueError("temporal access world position must be non-negative")
        if len(self.branch_ancestor_ids) != len(set(self.branch_ancestor_ids)):
            raise ValueError("branch ancestors must be distinct")
        if self.world_branch_id in self.branch_ancestor_ids:
            raise ValueError("current branch cannot be its own ancestor")
        return self


class TemporalEvidenceVisibleReference(LegacyContentAddressedModel):
    """One actor-visible opaque reference and bounded documentary metadata."""

    opaque_reference: NonEmptyStr
    version_id: NonEmptyStr
    title: NonEmptyStr
    snippet: NonEmptyStr
    citation: NonEmptyStr
    source_class: TemporalEvidenceSourceClass
    authority_class: TemporalEvidenceAuthorityClass
    event_start_seconds: int
    effective_from_seconds: int
    effective_to_seconds: int | None
    superseded: bool
    currently_applicable: bool


class TemporalFetchedEvidence(LegacyContentAddressedModel):
    """Actor-visible retained content returned only for an issued reference."""

    opaque_reference: NonEmptyStr
    version_id: NonEmptyStr
    title: NonEmptyStr
    citation: NonEmptyStr
    source_class: TemporalEvidenceSourceClass
    authority_class: TemporalEvidenceAuthorityClass
    content: NonEmptyStr
    superseded: bool
    currently_applicable: bool


class TemporalEvidenceAccessResult(LegacyContentAddressedModel):
    """Exact actor-visible projection of one search or fetch."""

    request_id: NonEmptyStr
    access_sequence: int
    operation: TemporalEvidenceAccessKind
    world_time_seconds: int
    normalized_query: str | None
    requested_reference: str | None
    references: tuple[TemporalEvidenceVisibleReference, ...]
    fetched_content: TemporalFetchedEvidence | None
    public_status: TemporalEvidenceAccessStatus
    truncated: bool
    visible_cost: RetrievalBudgetVector

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        if self.access_sequence <= 0 or self.world_time_seconds < 0:
            raise ValueError("access result position is invalid")
        if self.operation is TemporalEvidenceAccessKind.SEARCH:
            if self.normalized_query is None or self.requested_reference is not None:
                raise ValueError("search result requires only a normalized query")
            if self.fetched_content is not None:
                raise ValueError("search result cannot contain fetched content")
        else:
            if self.requested_reference is None or self.normalized_query is not None:
                raise ValueError("fetch result requires only a requested reference")
            if self.references:
                raise ValueError("fetch result cannot contain search references")
        if self.public_status is TemporalEvidenceAccessStatus.OK:
            success_payload = (
                bool(self.references)
                if self.operation is TemporalEvidenceAccessKind.SEARCH
                else self.fetched_content is not None
            )
            if not success_payload:
                raise ValueError("successful access result lacks visible evidence")
        elif self.references or self.fetched_content is not None:
            raise ValueError("unsuccessful access result must not contain evidence")
        return self


class IssuedTemporalReference(FrozenStrictModel):
    """Host-retained mapping for an opaque reference supplied to one tenure."""

    opaque_reference: NonEmptyStr
    evidence_version_id: NonEmptyStr


class TemporalRetrievalState(LegacyContentAddressedModel):
    """Durable per-tenure access state with exact remaining budget."""

    state_sequence: int
    previous_state_id: str | None
    reference_namespace_id: NonEmptyStr
    remaining_budget: RetrievalBudgetVector
    issued_references: tuple[IssuedTemporalReference, ...]
    access_result_ids: tuple[NonEmptyStr, ...]
    actor_event_ids: tuple[NonEmptyStr, ...]
    fetched_content_ids: tuple[NonEmptyStr, ...]
    unresolved_search_ids: tuple[NonEmptyStr, ...]
    installed_carrier_id: str | None

    @model_validator(mode="after")
    def validate_state(self) -> Self:
        if self.state_sequence < 0:
            raise ValueError("retrieval state sequence must be non-negative")
        if self.state_sequence == 0 and self.previous_state_id is not None:
            raise ValueError("initial retrieval state cannot have a parent")
        if self.state_sequence > 0 and self.previous_state_id is None:
            raise ValueError("advanced retrieval state requires a parent")
        references = tuple(item.opaque_reference for item in self.issued_references)
        if len(references) != len(set(references)):
            raise ValueError("issued opaque references must be distinct")
        for label, values in (
            ("access results", self.access_result_ids),
            ("actor events", self.actor_event_ids),
            ("fetched content", self.fetched_content_ids),
            ("unresolved searches", self.unresolved_search_ids),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"{label} must not contain duplicate identities")
        return self


class TemporalEvidenceAccessReceipt(LegacyContentAddressedModel):
    """Host-private receipt for one non-mutating evidence access."""

    receipt_sequence: int
    request_id: NonEmptyStr
    request_content_id: NonEmptyStr
    actor_id: NonEmptyStr
    actor_role: NonEmptyStr
    agent_tenure_id: NonEmptyStr
    session_id: NonEmptyStr
    run_id: NonEmptyStr
    episode_id: NonEmptyStr
    world_instance_id: NonEmptyStr
    world_branch_id: NonEmptyStr
    branch_ancestor_ids: tuple[NonEmptyStr, ...]
    world_state_id: NonEmptyStr
    world_commit_id: NonEmptyStr
    world_sequence: int
    world_time_seconds: int
    base_view_id: NonEmptyStr
    tool_contract_id: NonEmptyStr
    prior_information_set_id: NonEmptyStr
    resulting_information_set_id: NonEmptyStr
    corpus_snapshot_id: NonEmptyStr
    retrieval_policy_id: NonEmptyStr
    access_policy_id: NonEmptyStr
    availability_schedule_id: NonEmptyStr
    branch_namespace_policy_id: NonEmptyStr
    cost_policy_id: NonEmptyStr
    knowledge_frontier_fingerprint: NonEmptyStr
    access_context_id: NonEmptyStr
    original_query: str | None
    normalized_query: str | None
    requested_scope: str | None
    requested_limit: int | None
    requested_reference: str | None
    returned_version_ids: tuple[NonEmptyStr, ...]
    eligible_frontier_fingerprint: NonEmptyStr
    ranking_input_fingerprint: NonEmptyStr
    visible_result: TemporalEvidenceAccessResult
    public_status: TemporalEvidenceAccessStatus
    private_reason: TemporalEvidencePrivateReason
    budget_before: RetrievalBudgetVector
    budget_consumed: RetrievalBudgetVector
    budget_after: RetrievalBudgetVector

    @model_validator(mode="after")
    def validate_receipt(self) -> Self:
        if self.receipt_sequence != self.visible_result.access_sequence:
            raise ValueError("receipt and visible result sequence differ")
        if self.public_status is not self.visible_result.public_status:
            raise ValueError("receipt and visible result status differ")
        if self.visible_result.operation is TemporalEvidenceAccessKind.SEARCH:
            if self.requested_scope is None or self.requested_limit is None:
                raise ValueError("search receipt lacks its requested scope or limit")
            if self.requested_reference is not None:
                raise ValueError("search receipt cannot contain a requested reference")
        elif (
            self.requested_scope is not None
            or self.requested_limit is not None
            or self.original_query is not None
            or self.normalized_query is not None
        ):
            raise ValueError("fetch receipt cannot contain search arguments")
        _require_budget_equation(
            self.budget_before,
            self.budget_consumed,
            self.budget_after,
        )
        return self


class TemporalAccessDecision(FrozenStrictModel):
    """Pure gateway output ready for one durable publication transaction."""

    result: TemporalEvidenceAccessResult
    receipt: TemporalEvidenceAccessReceipt
    next_state: TemporalRetrievalState

    @model_validator(mode="after")
    def validate_decision(self) -> Self:
        if self.receipt.visible_result != self.result:
            raise ValueError("access decision receipt and result differ")
        if self.receipt.budget_after != self.next_state.remaining_budget:
            raise ValueError("access decision state and receipt budget differ")
        if self.next_state.previous_state_id is None:
            raise ValueError("access decision must advance retrieval state")
        return self


class TemporalInformationSetManifest(LegacyContentAddressedModel):
    """Strict temporal projection of the parent-owned information-set content."""

    information_set_id: NonEmptyStr
    base_view_id: NonEmptyStr
    agent_tenure_id: NonEmptyStr
    tenure_started_at_seconds: int
    observation_history_view_ids: tuple[NonEmptyStr, ...]
    continuity_carrier: NonEmptyStr
    workspace_tool_ids: tuple[NonEmptyStr, ...]
    visible_material_ids: tuple[NonEmptyStr, ...]

    @model_validator(mode="after")
    def validate_manifest(self) -> Self:
        if self.tenure_started_at_seconds < 0:
            raise ValueError("information-set tenure start must be non-negative")
        if not self.observation_history_view_ids:
            raise ValueError("information-set observation history must not be empty")
        if self.observation_history_view_ids[-1] != self.base_view_id:
            raise ValueError("information-set base view must be the latest observation")
        if not self.workspace_tool_ids or len(self.workspace_tool_ids) != len(set(self.workspace_tool_ids)):
            raise ValueError("information-set tools must be non-empty and distinct")
        if len(self.visible_material_ids) != len(set(self.visible_material_ids)):
            raise ValueError("information-set visible material must be distinct")
        return self


class TemporalActorVisibleEvent(LegacyContentAddressedModel):
    """One parent-valid actor-visible event projection for an access result."""

    event_id: NonEmptyStr
    event_sequence: int
    actor_id: NonEmptyStr
    agent_tenure_id: NonEmptyStr
    session_id: NonEmptyStr
    operation: TemporalEvidenceAccessKind
    access_result_id: NonEmptyStr
    public_status: TemporalEvidenceAccessStatus
    information_set_id: NonEmptyStr

    @model_validator(mode="after")
    def validate_event(self) -> Self:
        if self.event_sequence <= 0:
            raise ValueError("actor-visible event sequence must be positive")
        return self


class TemporalAccessPublication(FrozenStrictModel):
    """One cross-bound visible result, private receipt, event, and information set."""

    decision: TemporalAccessDecision
    event: TemporalActorVisibleEvent
    information_set: TemporalInformationSetManifest

    @model_validator(mode="after")
    def validate_publication(self) -> Self:
        if self.event.access_result_id != self.decision.result.content_sha256:
            raise ValueError("actor event and access result differ")
        if self.event.event_sequence != self.decision.result.access_sequence:
            raise ValueError("actor event and access result sequence differ")
        if self.event.information_set_id != self.information_set.information_set_id:
            raise ValueError("actor event and information set differ")
        if self.decision.receipt.resulting_information_set_id != self.information_set.information_set_id:
            raise ValueError("access receipt and information set differ")
        if self.event.event_id not in self.information_set.visible_material_ids:
            raise ValueError("information set does not bind the actor-visible event")
        return self

    def with_actor_event_bound(self) -> TemporalAccessPublication:
        """Return the canonical publication state with the event appended once."""

        state = self.decision.next_state
        event_ids = state.actor_event_ids
        if self.event.event_id not in event_ids:
            event_ids = (*event_ids, self.event.event_id)
        next_state = TemporalRetrievalState(
            state_sequence=state.state_sequence,
            previous_state_id=state.previous_state_id,
            reference_namespace_id=state.reference_namespace_id,
            remaining_budget=state.remaining_budget,
            issued_references=state.issued_references,
            access_result_ids=state.access_result_ids,
            actor_event_ids=event_ids,
            fetched_content_ids=state.fetched_content_ids,
            unresolved_search_ids=state.unresolved_search_ids,
            installed_carrier_id=state.installed_carrier_id,
        )
        return TemporalAccessPublication(
            decision=TemporalAccessDecision(
                result=self.decision.result,
                receipt=self.decision.receipt,
                next_state=next_state,
            ),
            event=self.event,
            information_set=self.information_set,
        )


class TemporalRetrievalStateCarrier(LegacyContentAddressedModel):
    """Sanitized actor-visible retrieval state carried to one fresh tenure."""

    carrier_policy_id: NonEmptyStr = "temporal-retrieval-carrier.v1"
    run_id: NonEmptyStr
    episode_id: NonEmptyStr
    world_branch_id: NonEmptyStr
    from_agent_tenure_id: NonEmptyStr
    from_session_id: NonEmptyStr
    to_agent_tenure_id: NonEmptyStr
    to_session_id: NonEmptyStr
    created_at_seconds: int
    include_fetched_content: bool
    access_results: tuple[TemporalEvidenceAccessResult, ...]
    unresolved_search_ids: tuple[NonEmptyStr, ...]
    remaining_budget: RetrievalBudgetVector

    @model_validator(mode="after")
    def validate_carrier(self) -> Self:
        if self.created_at_seconds < 0:
            raise ValueError("retrieval carrier time must be non-negative")
        if self.from_agent_tenure_id == self.to_agent_tenure_id:
            raise ValueError("retrieval carrier requires a fresh tenure")
        result_ids = tuple(item.content_sha256 for item in self.access_results)
        if len(result_ids) != len(set(result_ids)):
            raise ValueError("retrieval carrier results must be distinct")
        if not self.include_fetched_content and any(
            item.operation is TemporalEvidenceAccessKind.FETCH for item in self.access_results
        ):
            raise ValueError("retrieval-only carrier cannot contain fetched content")
        if not set(self.unresolved_search_ids).issubset(result_ids):
            raise ValueError("unresolved searches must be carried visible results")
        return self


class TemporalRetrievalHandoverReceipt(LegacyContentAddressedModel):
    """Host-private proof of one sanitized retrieval-carrier projection."""

    carrier_id: NonEmptyStr
    source_state_id: NonEmptyStr
    from_agent_tenure_id: NonEmptyStr
    from_session_id: NonEmptyStr
    to_agent_tenure_id: NonEmptyStr
    to_session_id: NonEmptyStr
    carried_result_ids: tuple[NonEmptyStr, ...]
    carried_reference_count: int
    remaining_budget: RetrievalBudgetVector

    @model_validator(mode="after")
    def validate_handover_receipt(self) -> Self:
        if self.carried_reference_count < 0:
            raise ValueError("carried reference count must be non-negative")
        if len(self.carried_result_ids) != len(set(self.carried_result_ids)):
            raise ValueError("carried result ids must be distinct")
        return self


class TemporalRetrievalHandoverInstallReceipt(LegacyContentAddressedModel):
    """Host-private proof that one fresh tenure installed one exact carrier."""

    carrier_id: NonEmptyStr
    target_session_key: NonEmptyStr
    prior_state_id: NonEmptyStr
    next_state_id: NonEmptyStr
    to_agent_tenure_id: NonEmptyStr
    to_session_id: NonEmptyStr


class TemporalEvidenceRelianceRecord(LegacyContentAddressedModel):
    """Explicit actor claim that one world action relied on supplied evidence."""

    action_request_id: NonEmptyStr
    action_name: NonEmptyStr
    actor_id: NonEmptyStr
    actor_role: NonEmptyStr
    agent_tenure_id: NonEmptyStr
    session_id: NonEmptyStr
    run_id: NonEmptyStr
    episode_id: NonEmptyStr
    world_instance_id: NonEmptyStr
    world_branch_id: NonEmptyStr
    branch_ancestor_ids: tuple[NonEmptyStr, ...]
    world_state_id: NonEmptyStr
    world_commit_id: NonEmptyStr
    world_sequence: int
    world_time_seconds: int
    base_view_id: NonEmptyStr
    tool_contract_id: NonEmptyStr
    information_set_id: NonEmptyStr
    relied_on_evidence_refs: tuple[NonEmptyStr, ...]
    evidence_version_ids: tuple[NonEmptyStr, ...]
    observed_access_result_ids: tuple[NonEmptyStr, ...]
    available_access_result_ids: tuple[NonEmptyStr, ...]
    recorded_evidence_refs: tuple[NonEmptyStr, ...] = ()
    accepted_evidence_refs: tuple[NonEmptyStr, ...] = ()

    @model_validator(mode="after")
    def validate_reliance(self) -> Self:
        if self.world_sequence < 0 or self.world_time_seconds < 0:
            raise ValueError("reliance world position must be non-negative")
        if not self.relied_on_evidence_refs:
            raise ValueError("reliance record must contain evidence")
        for label, values in (
            ("relied-on references", self.relied_on_evidence_refs),
            ("evidence versions", self.evidence_version_ids),
            ("observed results", self.observed_access_result_ids),
            ("available results", self.available_access_result_ids),
            ("recorded evidence", self.recorded_evidence_refs),
            ("accepted evidence", self.accepted_evidence_refs),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"{label} must be distinct")
        if len(self.relied_on_evidence_refs) != len(self.evidence_version_ids):
            raise ValueError("relied-on references and evidence versions differ")
        if not set(self.observed_access_result_ids).issubset(self.available_access_result_ids):
            raise ValueError("relied-on observations were not available at action time")
        return self


class TemporalRetrievalSessionManifest(LegacyContentAddressedModel):
    """Immutable identity of one tenure-scoped retrieval-state chain."""

    session_key: NonEmptyStr
    run_id: NonEmptyStr
    episode_id: NonEmptyStr
    world_branch_id: NonEmptyStr
    actor_id: NonEmptyStr
    agent_tenure_id: NonEmptyStr
    session_id: NonEmptyStr
    corpus_snapshot_id: NonEmptyStr
    initial_state_id: NonEmptyStr


class TemporalRetrievalStatePointer(FrozenStrictModel):
    """Mutable selector for one immutable tenure retrieval state."""

    session_key: NonEmptyStr
    state_sequence: int
    state_id: NonEmptyStr

    @model_validator(mode="after")
    def validate_pointer(self) -> Self:
        if self.state_sequence < 0:
            raise ValueError("retrieval state pointer sequence must be non-negative")
        return self


class TemporalInformationSetPointer(FrozenStrictModel):
    """Mutable selector for the latest immutable session information set."""

    session_key: NonEmptyStr
    information_set_id: NonEmptyStr
    information_set_content_id: NonEmptyStr


class TemporalAccessCommit(LegacyContentAddressedModel):
    """Immutable staged access commit selected by one tenure pointer."""

    session_key: NonEmptyStr
    request_id: NonEmptyStr
    request_content_id: NonEmptyStr
    prior_state_id: NonEmptyStr
    next_state_id: NonEmptyStr
    result_id: NonEmptyStr
    receipt_id: NonEmptyStr
    event_id: NonEmptyStr
    event_content_id: NonEmptyStr
    information_set_id: NonEmptyStr
    information_set_content_id: NonEmptyStr
    fetched_content_id: str | None


def temporal_actor_event_id(
    *,
    request_id: str,
    access_sequence: int,
    context: TemporalAccessContext,
) -> str:
    """Return a stable visible event id without hidden corpus or frontier inputs."""

    return canonical_json_sha256(
        {
            "event_kind": "temporal_evidence_access",
            "request_id": request_id,
            "access_sequence": access_sequence,
            "actor_id": context.actor_id,
            "agent_tenure_id": context.agent_tenure_id,
            "session_id": context.session_id,
        }
    )


def _require_budget_equation(
    before: RetrievalBudgetVector,
    consumed: RetrievalBudgetVector,
    after: RetrievalBudgetVector,
) -> None:
    for field_name in RetrievalBudgetVector.model_fields:
        if getattr(before, field_name) - getattr(consumed, field_name) != getattr(after, field_name):
            raise ValueError(f"retrieval budget is not conserved for {field_name}")
