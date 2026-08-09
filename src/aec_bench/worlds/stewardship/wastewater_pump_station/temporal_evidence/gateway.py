# ABOUTME: Applies canonical filter-before-rank search and safe opaque-reference fetch.
# ABOUTME: Produces deterministic visible results and private receipts without world mutation.

from __future__ import annotations

import re
import unicodedata
from collections import Counter

from aec_bench.contracts.harness_kernel import canonical_content_sha256
from aec_bench.worlds.stewardship.wastewater_pump_station.temporal_evidence.access_models import (
    IssuedTemporalReference,
    TemporalAccessContext,
    TemporalAccessDecision,
    TemporalEvidenceAccessKind,
    TemporalEvidenceAccessReceipt,
    TemporalEvidenceAccessResult,
    TemporalEvidenceAccessStatus,
    TemporalEvidencePrivateReason,
    TemporalEvidenceVisibleReference,
    TemporalFetchedEvidence,
    TemporalRetrievalState,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.temporal_evidence.models import (
    RetrievalBudgetVector,
    TemporalCostPolicy,
    TemporalEvidenceBundle,
    TemporalEvidenceEventKind,
    TemporalEvidenceVersion,
)

_TOKEN = re.compile(r"[a-z0-9]+")
_UNTRUSTED_PREFIX = "[UNTRUSTED DOCUMENTARY EVIDENCE] "


class TemporalEvidenceGateway:
    """Pure deterministic gateway over one complete immutable corpus snapshot."""

    def __init__(self, bundle: TemporalEvidenceBundle) -> None:
        self._bundle = TemporalEvidenceBundle.model_validate(bundle.model_dump(mode="json"))
        self._versions = {item.version_id: item for item in self._bundle.versions}

    def search(
        self,
        *,
        request_id: str,
        query: str,
        scope: str,
        limit: int,
        context: TemporalAccessContext,
        state: TemporalRetrievalState,
        resulting_information_set_id: str,
    ) -> TemporalAccessDecision:
        """Return an ordered actor-visible result after host-owned frontier filtering."""

        normalized = _normalize_query(query)
        request_content_id = canonical_content_sha256(
            {
                "kind": TemporalEvidenceAccessKind.SEARCH.value,
                "request_id": request_id,
                "query": query,
                "scope": scope,
                "limit": limit,
                "context": context.model_dump(mode="json"),
                "state_id": state.content_sha256,
            }
        )
        invalid = (
            not normalized
            or len(query) > self._bundle.retrieval_policy.maximum_query_characters
            or scope not in self._bundle.access_policy.allowed_scopes
            or limit <= 0
            or limit > self._bundle.retrieval_policy.maximum_results
        )
        candidates = self._matching_versions(normalized, scope=scope) if not invalid else ()
        eligible = tuple(item for item in candidates if self._is_accessible(item, context))
        ranked = self._rank(eligible, normalized)
        visible_versions = ranked[:limit]
        references = tuple(
            self._visible_reference(item, context=context, state=state, query=normalized) for item in visible_versions
        )
        private_reason = (
            TemporalEvidencePrivateReason.INVALID_REQUEST
            if invalid
            else TemporalEvidencePrivateReason.MATCH
            if references
            else self._negative_reason(candidates, context)
        )
        status = TemporalEvidenceAccessStatus.OK if references else TemporalEvidenceAccessStatus.NO_ACCESSIBLE_RESULT
        consumed = _visible_cost(
            references=references,
            fetched_content=None,
            cost_policy=self._bundle.cost_policy,
        )
        if not _budget_allows(state.remaining_budget, consumed):
            references = ()
            consumed = _zero_budget()
            private_reason = TemporalEvidencePrivateReason.BUDGET_EXHAUSTED
            status = TemporalEvidenceAccessStatus.RETRIEVAL_UNAVAILABLE
        return self._decision(
            request_id=request_id,
            request_content_id=request_content_id,
            context=context,
            state=state,
            resulting_information_set_id=resulting_information_set_id,
            operation=TemporalEvidenceAccessKind.SEARCH,
            original_query=query,
            normalized_query=normalized,
            requested_scope=scope,
            requested_limit=limit,
            requested_reference=None,
            references=references,
            fetched_content=None,
            public_status=status,
            private_reason=private_reason,
            truncated=len(ranked) > len(references),
            consumed=consumed,
            eligible=tuple(item for item in self._bundle.versions if self._is_accessible(item, context)),
            ranking_versions=eligible,
        )

    def fetch(
        self,
        *,
        request_id: str,
        reference: str,
        context: TemporalAccessContext,
        state: TemporalRetrievalState,
        resulting_information_set_id: str,
    ) -> TemporalAccessDecision:
        """Fetch content only for a reference already supplied to this tenure."""

        request_content_id = canonical_content_sha256(
            {
                "kind": TemporalEvidenceAccessKind.FETCH.value,
                "request_id": request_id,
                "reference": reference,
                "context": context.model_dump(mode="json"),
                "state_id": state.content_sha256,
            }
        )
        issued = next(
            (item for item in state.issued_references if item.opaque_reference == reference),
            None,
        )
        version = self._versions.get(issued.evidence_version_id) if issued is not None else None
        accessible = version is not None and self._is_accessible(version, context)
        fetched = self._fetched_content(version, reference=reference, context=context) if accessible else None
        private_reason = (
            TemporalEvidencePrivateReason.MATCH
            if fetched is not None
            else TemporalEvidencePrivateReason.UNISSUED_REFERENCE
            if issued is None
            else TemporalEvidencePrivateReason.SOURCE_UNAVAILABLE
        )
        status = (
            TemporalEvidenceAccessStatus.OK
            if fetched is not None
            else TemporalEvidenceAccessStatus.NO_ACCESSIBLE_RESULT
        )
        consumed = _visible_cost(
            references=(),
            fetched_content=fetched,
            cost_policy=self._bundle.cost_policy,
        )
        if not _budget_allows(state.remaining_budget, consumed):
            fetched = None
            consumed = _zero_budget()
            private_reason = TemporalEvidencePrivateReason.BUDGET_EXHAUSTED
            status = TemporalEvidenceAccessStatus.RETRIEVAL_UNAVAILABLE
        eligible = tuple(item for item in self._bundle.versions if self._is_accessible(item, context))
        return self._decision(
            request_id=request_id,
            request_content_id=request_content_id,
            context=context,
            state=state,
            resulting_information_set_id=resulting_information_set_id,
            operation=TemporalEvidenceAccessKind.FETCH,
            original_query=None,
            normalized_query=None,
            requested_scope=None,
            requested_limit=None,
            requested_reference=reference,
            references=(),
            fetched_content=fetched,
            public_status=status,
            private_reason=private_reason,
            truncated=False,
            consumed=consumed,
            eligible=eligible,
            ranking_versions=(version,) if accessible and version is not None else (),
        )

    def accessible_versions(
        self,
        context: TemporalAccessContext,
    ) -> tuple[TemporalEvidenceVersion, ...]:
        """Return the complete host-private deterministic frontier for verification."""

        return tuple(item for item in self._bundle.versions if self._is_accessible(item, context))

    def _decision(
        self,
        *,
        request_id: str,
        request_content_id: str,
        context: TemporalAccessContext,
        state: TemporalRetrievalState,
        resulting_information_set_id: str,
        operation: TemporalEvidenceAccessKind,
        original_query: str | None,
        normalized_query: str | None,
        requested_scope: str | None,
        requested_limit: int | None,
        requested_reference: str | None,
        references: tuple[TemporalEvidenceVisibleReference, ...],
        fetched_content: TemporalFetchedEvidence | None,
        public_status: TemporalEvidenceAccessStatus,
        private_reason: TemporalEvidencePrivateReason,
        truncated: bool,
        consumed: RetrievalBudgetVector,
        eligible: tuple[TemporalEvidenceVersion, ...],
        ranking_versions: tuple[TemporalEvidenceVersion, ...],
    ) -> TemporalAccessDecision:
        after = _subtract_budget(state.remaining_budget, consumed)
        result = TemporalEvidenceAccessResult(
            request_id=request_id,
            access_sequence=state.state_sequence + 1,
            operation=operation,
            world_time_seconds=context.world_time_seconds,
            normalized_query=normalized_query,
            requested_reference=requested_reference,
            references=references,
            fetched_content=fetched_content,
            public_status=public_status,
            truncated=truncated,
            visible_cost=consumed,
        )
        frontier_fingerprint = canonical_content_sha256(
            {
                "world_instance_id": context.world_instance_id,
                "world_branch_id": context.world_branch_id,
                "world_state_id": context.world_state_id,
                "world_time_seconds": context.world_time_seconds,
                "actor_id": context.actor_id,
                "corpus_snapshot_id": self._bundle.corpus_manifest.content_sha256,
                "access_policy_id": self._bundle.access_policy.content_sha256,
                "availability_schedule_id": self._bundle.availability.content_sha256,
                "branch_policy_id": self._bundle.branch_policy.content_sha256,
                "retrieval_policy_id": self._bundle.retrieval_policy.content_sha256,
            }
        )
        access_context_id = canonical_content_sha256(
            {
                "knowledge_frontier_fingerprint": frontier_fingerprint,
                "agent_tenure_id": context.agent_tenure_id,
                "session_id": context.session_id,
                "tool_contract_id": context.tool_contract_id,
                "remaining_budget": state.remaining_budget.model_dump(mode="json"),
            }
        )
        eligible_fingerprint = canonical_content_sha256(
            [item.content_sha256 for item in sorted(eligible, key=lambda item: item.version_id)]
        )
        ranking_fingerprint = canonical_content_sha256(
            {
                "normalized_query": normalized_query,
                "versions": [item.content_sha256 for item in ranking_versions],
            }
        )
        returned_version_ids = tuple(item.version_id for item in references)
        if fetched_content is not None:
            returned_version_ids = (fetched_content.version_id,)
        receipt = TemporalEvidenceAccessReceipt(
            receipt_sequence=result.access_sequence,
            request_id=request_id,
            request_content_id=request_content_id,
            actor_id=context.actor_id,
            actor_role=context.actor_role,
            agent_tenure_id=context.agent_tenure_id,
            session_id=context.session_id,
            run_id=context.run_id,
            episode_id=context.episode_id,
            world_instance_id=context.world_instance_id,
            world_branch_id=context.world_branch_id,
            branch_ancestor_ids=context.branch_ancestor_ids,
            world_state_id=context.world_state_id,
            world_commit_id=context.world_commit_id,
            world_sequence=context.world_sequence,
            world_time_seconds=context.world_time_seconds,
            base_view_id=context.base_view_id,
            tool_contract_id=context.tool_contract_id,
            prior_information_set_id=context.prior_information_set_id,
            resulting_information_set_id=resulting_information_set_id,
            corpus_snapshot_id=self._bundle.corpus_manifest.content_sha256,
            retrieval_policy_id=self._bundle.retrieval_policy.content_sha256,
            access_policy_id=self._bundle.access_policy.content_sha256,
            availability_schedule_id=self._bundle.availability.content_sha256,
            branch_namespace_policy_id=self._bundle.branch_policy.content_sha256,
            cost_policy_id=self._bundle.cost_policy.content_sha256,
            knowledge_frontier_fingerprint=frontier_fingerprint,
            access_context_id=access_context_id,
            original_query=original_query,
            normalized_query=normalized_query,
            requested_scope=requested_scope,
            requested_limit=requested_limit,
            requested_reference=requested_reference,
            returned_version_ids=returned_version_ids,
            eligible_frontier_fingerprint=eligible_fingerprint,
            ranking_input_fingerprint=ranking_fingerprint,
            visible_result=result,
            public_status=public_status,
            private_reason=private_reason,
            budget_before=state.remaining_budget,
            budget_consumed=consumed,
            budget_after=after,
        )
        issued = list(state.issued_references)
        by_reference = {item.opaque_reference: item for item in issued}
        for item in references:
            by_reference[item.opaque_reference] = IssuedTemporalReference(
                opaque_reference=item.opaque_reference,
                evidence_version_id=item.version_id,
            )
        fetched_ids = state.fetched_content_ids
        if fetched_content is not None and fetched_content.content_sha256 not in fetched_ids:
            fetched_ids = (*fetched_ids, fetched_content.content_sha256)
        unresolved = state.unresolved_search_ids
        if operation is TemporalEvidenceAccessKind.SEARCH and public_status is not TemporalEvidenceAccessStatus.OK:
            unresolved = (*unresolved, result.content_sha256)
        next_state = TemporalRetrievalState(
            state_sequence=state.state_sequence + 1,
            previous_state_id=state.content_sha256,
            reference_namespace_id=state.reference_namespace_id,
            remaining_budget=after,
            issued_references=tuple(sorted(by_reference.values(), key=lambda item: item.opaque_reference)),
            access_result_ids=(*state.access_result_ids, result.content_sha256),
            actor_event_ids=state.actor_event_ids,
            fetched_content_ids=fetched_ids,
            unresolved_search_ids=unresolved,
            installed_carrier_id=state.installed_carrier_id,
        )
        return TemporalAccessDecision(result=result, receipt=receipt, next_state=next_state)

    def _matching_versions(
        self,
        normalized_query: str,
        *,
        scope: str,
    ) -> tuple[TemporalEvidenceVersion, ...]:
        tokens = _tokens(normalized_query)
        return tuple(
            item
            for item in self._bundle.versions
            if (scope == "all" or scope in item.scope_labels)
            and any(token in _searchable_text(item) for token in tokens)
        )

    def _rank(
        self,
        eligible: tuple[TemporalEvidenceVersion, ...],
        normalized_query: str,
    ) -> tuple[TemporalEvidenceVersion, ...]:
        query_tokens = _tokens(normalized_query)

        def rank_key(item: TemporalEvidenceVersion) -> tuple[int, str]:
            counts = Counter(_tokens(_searchable_text(item)))
            score = sum(counts[token] for token in query_tokens)
            return (-score, item.version_id)

        return tuple(sorted(eligible, key=rank_key))

    def _is_accessible(
        self,
        version: TemporalEvidenceVersion,
        context: TemporalAccessContext,
    ) -> bool:
        if context.actor_role not in self._bundle.access_policy.actor_roles:
            return False
        if context.actor_role not in version.access_roles:
            return False
        visible_namespaces = {
            self._bundle.branch_policy.shared_namespace,
            context.world_branch_id,
            *context.branch_ancestor_ids,
        }
        if version.branch_namespace not in visible_namespaces:
            return False
        events = tuple(
            event
            for event in self._bundle.availability.events
            if event.evidence_version_id == version.version_id and event.scheduled_seconds <= context.world_time_seconds
        )
        searchable = any(
            event.kind is TemporalEvidenceEventKind.SEARCHABLE
            and (not event.actor_roles or context.actor_role in event.actor_roles)
            for event in events
        )
        unavailable = any(
            event.kind in {TemporalEvidenceEventKind.ACCESS_REVOKED, TemporalEvidenceEventKind.SOURCE_UNAVAILABLE}
            for event in events
        )
        return searchable and not unavailable

    def _negative_reason(
        self,
        candidates: tuple[TemporalEvidenceVersion, ...],
        context: TemporalAccessContext,
    ) -> TemporalEvidencePrivateReason:
        if any(item.available_at_seconds > context.world_time_seconds for item in candidates):
            return TemporalEvidencePrivateReason.FUTURE_EVIDENCE
        visible_namespaces = {
            self._bundle.branch_policy.shared_namespace,
            context.world_branch_id,
            *context.branch_ancestor_ids,
        }
        if any(item.branch_namespace not in visible_namespaces for item in candidates):
            return TemporalEvidencePrivateReason.BRANCH_MISMATCH
        if any(context.actor_role not in item.access_roles for item in candidates):
            return TemporalEvidencePrivateReason.ACCESS_DENIED
        return TemporalEvidencePrivateReason.NO_MATCH

    def _visible_reference(
        self,
        version: TemporalEvidenceVersion,
        *,
        context: TemporalAccessContext,
        state: TemporalRetrievalState,
        query: str,
    ) -> TemporalEvidenceVisibleReference:
        opaque_reference = canonical_content_sha256(
            {
                "reference_namespace_id": state.reference_namespace_id,
                "evidence_content_id": version.content_sha256,
            }
        )
        return TemporalEvidenceVisibleReference(
            opaque_reference=opaque_reference,
            version_id=version.version_id,
            title=version.title,
            snippet=_snippet(version, query, self._bundle.retrieval_policy.maximum_snippet_characters),
            citation=version.citation,
            source_class=version.source_class,
            authority_class=version.authority_class,
            event_start_seconds=version.event_start_seconds,
            effective_from_seconds=version.effective_from_seconds,
            effective_to_seconds=version.effective_to_seconds,
            superseded=_superseded(version, context.world_time_seconds),
            currently_applicable=_applicable(version, context.world_time_seconds),
        )

    def _fetched_content(
        self,
        version: TemporalEvidenceVersion | None,
        *,
        reference: str,
        context: TemporalAccessContext,
    ) -> TemporalFetchedEvidence | None:
        if version is None or version.content_text is None:
            return None
        return TemporalFetchedEvidence(
            opaque_reference=reference,
            version_id=version.version_id,
            title=version.title,
            citation=version.citation,
            source_class=version.source_class,
            authority_class=version.authority_class,
            content=_UNTRUSTED_PREFIX + version.content_text,
            superseded=_superseded(version, context.world_time_seconds),
            currently_applicable=_applicable(version, context.world_time_seconds),
        )


def _normalize_query(query: str) -> str:
    normalized = unicodedata.normalize("NFKC", query).lower()
    return " ".join(normalized.split())


def _tokens(value: str) -> tuple[str, ...]:
    return tuple(_TOKEN.findall(value.lower()))


def _searchable_text(version: TemporalEvidenceVersion) -> str:
    return f"{version.title} {version.content_text or ''}".lower()


def _snippet(version: TemporalEvidenceVersion, query: str, maximum: int) -> str:
    content = f"{version.title}. {version.content_text or version.citation}"
    lowered = content.lower()
    positions = [lowered.find(token) for token in _tokens(query) if lowered.find(token) >= 0]
    start = max(0, (min(positions) if positions else 0) - maximum // 4)
    selected = content[start : start + maximum]
    return _UNTRUSTED_PREFIX + selected


def _superseded(version: TemporalEvidenceVersion, world_time_seconds: int) -> bool:
    return version.superseded_at_seconds is not None and version.superseded_at_seconds <= world_time_seconds


def _applicable(version: TemporalEvidenceVersion, world_time_seconds: int) -> bool:
    return version.effective_from_seconds <= world_time_seconds and (
        version.effective_to_seconds is None or world_time_seconds <= version.effective_to_seconds
    )


def _visible_cost(
    *,
    references: tuple[TemporalEvidenceVisibleReference, ...],
    fetched_content: TemporalFetchedEvidence | None,
    cost_policy: TemporalCostPolicy,
) -> RetrievalBudgetVector:
    visible_text = "".join(item.snippet for item in references)
    if fetched_content is not None:
        visible_text += fetched_content.content
    return RetrievalBudgetVector(
        calls=1,
        returned_references=len(references),
        visible_bytes=len(visible_text.encode("utf-8")),
        visible_tokens=len(re.findall(r"\w+|[^\w\s]", visible_text)),
        turns=1,
        simulated_duration_seconds=cost_policy.simulated_duration_seconds,
        provider_spend_microusd=cost_policy.provider_spend_microusd,
    )


def _zero_budget() -> RetrievalBudgetVector:
    return RetrievalBudgetVector(
        calls=0,
        returned_references=0,
        visible_bytes=0,
        visible_tokens=0,
        turns=0,
        simulated_duration_seconds=0,
        provider_spend_microusd=0,
    )


def _budget_allows(before: RetrievalBudgetVector, consumed: RetrievalBudgetVector) -> bool:
    return all(
        getattr(before, field_name) >= getattr(consumed, field_name)
        for field_name in RetrievalBudgetVector.model_fields
    )


def _subtract_budget(
    before: RetrievalBudgetVector,
    consumed: RetrievalBudgetVector,
) -> RetrievalBudgetVector:
    return RetrievalBudgetVector(
        **{
            field_name: getattr(before, field_name) - getattr(consumed, field_name)
            for field_name in RetrievalBudgetVector.model_fields
        }
    )
