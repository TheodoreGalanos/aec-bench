# ABOUTME: Tests durable atomic temporal access publication, retry, and crash recovery.
# ABOUTME: Uses real filesystem artifacts and process-style repository restart without mocks.

from __future__ import annotations

from pathlib import Path

import pytest

from aec_bench.worlds.stewardship.wastewater_pump_station import (
    load_reference_package,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.temporal_evidence import (
    REFERENCE_WORLD_TIME_SECONDS,
    TemporalAccessContext,
    TemporalAccessPublication,
    TemporalActorVisibleEvent,
    TemporalEvidenceGateway,
    TemporalEvidenceIntegrityError,
    TemporalEvidenceRepository,
    TemporalInformationSetManifest,
    build_reference_temporal_evidence_bundle,
    temporal_actor_event_id,
)


def _context() -> TemporalAccessContext:
    return TemporalAccessContext(
        run_id="run-temporal",
        episode_id="episode-temporal",
        world_instance_id="station-001",
        world_branch_id="branch-temporal",
        world_state_id="state-temporal",
        world_commit_id="commit-temporal",
        world_sequence=4,
        world_time_seconds=REFERENCE_WORLD_TIME_SECONDS + 3_600,
        actor_id="station-steward",
        actor_role="station-steward",
        agent_tenure_id="tenure-temporal",
        session_id="session-temporal",
        base_view_id="view-temporal",
        prior_information_set_id="information-set-before-access",
        tool_contract_id="pump-station-temporal-tools.v1",
        branch_ancestor_ids=(),
    )


def _publication(
    repository: TemporalEvidenceRepository,
    gateway: TemporalEvidenceGateway,
    *,
    request_id: str = "search-procedure",
    query: str = "pump obstruction procedure",
) -> TemporalAccessPublication:
    context = _context()
    state = repository.open_retrieval_state(context)
    event_id = temporal_actor_event_id(
        request_id=request_id,
        access_sequence=state.state_sequence + 1,
        context=context,
    )
    information_set = TemporalInformationSetManifest(
        information_set_id=f"information-set-after-{request_id}",
        base_view_id=context.base_view_id,
        agent_tenure_id=context.agent_tenure_id,
        tenure_started_at_seconds=context.world_time_seconds,
        observation_history_view_ids=(context.base_view_id,),
        continuity_carrier="current_actor_view",
        workspace_tool_ids=("search_evidence", "fetch_evidence", "continue_operation"),
        visible_material_ids=(*state.actor_event_ids, event_id),
    )
    decision = gateway.search(
        request_id=request_id,
        query=query,
        scope="procedures",
        limit=5,
        context=context,
        state=state,
        resulting_information_set_id=information_set.information_set_id,
    )
    event = TemporalActorVisibleEvent(
        event_id=event_id,
        event_sequence=decision.result.access_sequence,
        actor_id=context.actor_id,
        agent_tenure_id=context.agent_tenure_id,
        session_id=context.session_id,
        operation=decision.result.operation,
        access_result_id=decision.result.content_sha256,
        public_status=decision.result.public_status,
        information_set_id=information_set.information_set_id,
    )
    return TemporalAccessPublication(
        decision=decision,
        event=event,
        information_set=information_set,
    )


def test_access_retry_after_restart_returns_one_terminal_transaction(
    tmp_path: Path,
) -> None:
    package = load_reference_package()
    bundle = build_reference_temporal_evidence_bundle(
        package,
        world_branch_id="branch-temporal",
    )
    root = tmp_path / "temporal-evidence"
    repository = TemporalEvidenceRepository(root)
    repository.initialize(bundle, package=package)
    gateway = TemporalEvidenceGateway(bundle)
    publication = _publication(repository, gateway)

    first = repository.commit_access(publication, context=_context())
    restarted = TemporalEvidenceRepository(root)
    restarted.load_bundle(package=package)
    repeated = restarted.commit_access(publication, context=_context())
    recovered = restarted.recover_access("search-procedure", context=_context())
    current = restarted.load_retrieval_state(_context())

    assert repeated == first == recovered
    assert current.state_sequence == 1
    assert current.remaining_budget == publication.decision.receipt.budget_after
    assert len(tuple((root / "private" / "transactions").glob("*.json"))) == 1
    assert len(tuple((root / "public" / "results").glob("*.json"))) == 1
    assert len(tuple((root / "private" / "receipts").glob("*.json"))) == 1
    assert len(tuple((root / "public" / "events").glob("*.json"))) == 1


def test_staged_access_recovers_after_restart_without_partial_authority(
    tmp_path: Path,
) -> None:
    package = load_reference_package()
    bundle = build_reference_temporal_evidence_bundle(
        package,
        world_branch_id="branch-temporal",
    )
    root = tmp_path / "temporal-evidence"
    repository = TemporalEvidenceRepository(root)
    repository.initialize(bundle, package=package)
    publication = _publication(repository, TemporalEvidenceGateway(bundle))

    staged = repository.stage_access(publication, context=_context())
    assert repository.load_retrieval_state(_context()).state_sequence == 0
    restarted = TemporalEvidenceRepository(root)
    recovered = restarted.recover_access("search-procedure", context=_context())

    assert recovered == publication.with_actor_event_bound()
    assert restarted.load_retrieval_state(_context()).state_sequence == 1
    assert staged.next_state_id == recovered.decision.next_state.content_sha256


def test_reused_request_identity_rejects_different_access_content(
    tmp_path: Path,
) -> None:
    package = load_reference_package()
    bundle = build_reference_temporal_evidence_bundle(
        package,
        world_branch_id="branch-temporal",
    )
    repository = TemporalEvidenceRepository(tmp_path / "temporal-evidence")
    repository.initialize(bundle, package=package)
    gateway = TemporalEvidenceGateway(bundle)
    first = _publication(repository, gateway)
    repository.commit_access(first, context=_context())
    other = TemporalEvidenceRepository(tmp_path / "other-state")
    other.initialize(bundle, package=package)
    conflicting = _publication(
        other,
        gateway,
        request_id="search-procedure",
        query="isolation bulletin",
    )

    with pytest.raises(TemporalEvidenceIntegrityError, match="request identity conflict"):
        repository.commit_access(conflicting, context=_context())
