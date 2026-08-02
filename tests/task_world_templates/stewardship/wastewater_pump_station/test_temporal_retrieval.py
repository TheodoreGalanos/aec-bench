# ABOUTME: Tests deterministic time-bound search, fetch, ranking, and retrieval privacy.
# ABOUTME: Attacks future leakage, branch contamination, guessed references, and budget drift.

from __future__ import annotations

from aec_bench.contracts.harness_kernel import canonical_content_sha256
from aec_bench.task_world_templates.stewardship.wastewater_pump_station import (
    load_reference_package,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.temporal_evidence import (
    REFERENCE_WORLD_TIME_SECONDS,
    RetrievalBudgetVector,
    TemporalAccessContext,
    TemporalEvidenceAccessKind,
    TemporalEvidenceAccessStatus,
    TemporalEvidenceGateway,
    TemporalEvidencePrivateReason,
    TemporalRetrievalState,
    build_reference_temporal_evidence_bundle,
)


def _context(*, world_time_seconds: int, branch_id: str = "branch-temporal") -> TemporalAccessContext:
    return TemporalAccessContext(
        run_id="run-temporal",
        episode_id="episode-temporal",
        world_instance_id="station-001",
        world_branch_id=branch_id,
        world_state_id="state-temporal",
        world_commit_id="commit-temporal",
        world_sequence=4,
        world_time_seconds=world_time_seconds,
        actor_id="station-steward",
        actor_role="station-steward",
        agent_tenure_id="tenure-temporal",
        session_id="session-temporal",
        base_view_id="view-temporal",
        prior_information_set_id="information-set-before-access",
        tool_contract_id="pump-station-temporal-tools.v1",
        branch_ancestor_ids=(),
    )


def _state() -> TemporalRetrievalState:
    return TemporalRetrievalState(
        state_sequence=0,
        previous_state_id=None,
        reference_namespace_id=canonical_content_sha256(
            {"session": "session-temporal", "tenure": "tenure-temporal"},
        ),
        remaining_budget=RetrievalBudgetVector(
            calls=20,
            returned_references=50,
            visible_bytes=40_000,
            visible_tokens=10_000,
            turns=20,
            simulated_duration_seconds=0,
            provider_spend_microusd=0,
        ),
        issued_references=(),
        access_result_ids=(),
        actor_event_ids=(),
        fetched_content_ids=(),
        unresolved_search_ids=(),
        installed_carrier_id=None,
    )


def test_future_and_sibling_evidence_use_one_non_leaking_public_result() -> None:
    package = load_reference_package()
    bundle = build_reference_temporal_evidence_bundle(
        package,
        world_branch_id="branch-temporal",
    )
    gateway = TemporalEvidenceGateway(bundle)

    before = gateway.search(
        request_id="search-delayed",
        query="delayed condition report",
        scope="condition",
        limit=5,
        context=_context(world_time_seconds=REFERENCE_WORLD_TIME_SECONDS),
        state=_state(),
        resulting_information_set_id="information-set-after-search",
    )
    sibling = gateway.search(
        request_id="search-delayed",
        query="delayed condition report",
        scope="condition",
        limit=5,
        context=_context(
            world_time_seconds=REFERENCE_WORLD_TIME_SECONDS + 3_600,
            branch_id="branch-sibling",
        ),
        state=_state(),
        resulting_information_set_id="information-set-after-search",
    )
    after = gateway.search(
        request_id="search-delayed",
        query="delayed condition report",
        scope="condition",
        limit=5,
        context=_context(world_time_seconds=REFERENCE_WORLD_TIME_SECONDS + 3_600),
        state=_state(),
        resulting_information_set_id="information-set-after-search",
    )

    assert before.result.public_status is TemporalEvidenceAccessStatus.NO_ACCESSIBLE_RESULT
    assert sibling.result.public_status is TemporalEvidenceAccessStatus.NO_ACCESSIBLE_RESULT
    assert before.result.references == sibling.result.references == ()
    assert before.result.fetched_content is sibling.result.fetched_content is None
    assert before.receipt.private_reason is TemporalEvidencePrivateReason.FUTURE_EVIDENCE
    assert sibling.receipt.private_reason is TemporalEvidencePrivateReason.BRANCH_MISMATCH
    assert after.result.public_status is TemporalEvidenceAccessStatus.OK
    assert len(after.result.references) == 1
    assert "delayed" in after.result.references[0].snippet.lower()


def test_search_replay_fetch_and_budget_are_deterministic_and_safe() -> None:
    package = load_reference_package()
    bundle = build_reference_temporal_evidence_bundle(
        package,
        world_branch_id="branch-temporal",
    )
    gateway = TemporalEvidenceGateway(bundle)
    context = _context(world_time_seconds=REFERENCE_WORLD_TIME_SECONDS + 3_600)
    state = _state()

    first = gateway.search(
        request_id="search-procedure",
        query="pump obstruction procedure",
        scope="procedures",
        limit=5,
        context=context,
        state=state,
        resulting_information_set_id="information-set-after-search",
    )
    repeated = gateway.search(
        request_id="search-procedure",
        query="pump obstruction procedure",
        scope="procedures",
        limit=5,
        context=context,
        state=state,
        resulting_information_set_id="information-set-after-search",
    )

    assert first == repeated
    assert first.result.operation is TemporalEvidenceAccessKind.SEARCH
    assert first.result.references
    assert first.receipt.budget_before == state.remaining_budget
    assert first.receipt.budget_after == first.next_state.remaining_budget
    assert first.receipt.budget_consumed.calls == 1
    assert first.receipt.budget_before.calls - first.receipt.budget_consumed.calls == first.receipt.budget_after.calls
    assert all(
        item.snippet.startswith("[UNTRUSTED DOCUMENTARY EVIDENCE]")
        for item in first.result.references
    )

    selected = first.result.references[0]
    fetched = gateway.fetch(
        request_id="fetch-procedure",
        reference=selected.opaque_reference,
        context=context,
        state=first.next_state,
        resulting_information_set_id="information-set-after-fetch",
    )
    guessed = gateway.fetch(
        request_id="fetch-guessed",
        reference="0" * 64,
        context=context,
        state=first.next_state,
        resulting_information_set_id="information-set-after-guessed-fetch",
    )

    assert fetched.result.public_status is TemporalEvidenceAccessStatus.OK
    assert fetched.result.fetched_content is not None
    assert fetched.result.fetched_content.content.startswith("[UNTRUSTED DOCUMENTARY EVIDENCE]")
    assert guessed.result.public_status is TemporalEvidenceAccessStatus.NO_ACCESSIBLE_RESULT
    assert guessed.result.fetched_content is None
    assert guessed.receipt.private_reason is TemporalEvidencePrivateReason.UNISSUED_REFERENCE


def test_superseded_versions_remain_explicit_and_searchable() -> None:
    package = load_reference_package()
    gateway = TemporalEvidenceGateway(
        build_reference_temporal_evidence_bundle(
            package,
            world_branch_id="branch-temporal",
        )
    )
    result = gateway.search(
        request_id="search-original-interval",
        query="original verification interval",
        scope="procedures",
        limit=5,
        context=_context(world_time_seconds=REFERENCE_WORLD_TIME_SECONDS + 3_600),
        state=_state(),
        resulting_information_set_id="information-set-after-search",
    )

    assert result.result.public_status is TemporalEvidenceAccessStatus.OK
    assert result.result.references[0].version_id == "pump-a-maintenance-procedure.v1"
    assert result.result.references[0].superseded is True
    assert result.result.references[0].currently_applicable is False
