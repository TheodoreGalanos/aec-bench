# ABOUTME: Tests the ASW-8 temporal template, delayed Pump C note, and branch realization.
# ABOUTME: Proves the same query changes only at the declared document-review clock stop.

from __future__ import annotations

from aec_bench.task_world_templates.stewardship.wastewater_pump_station.reference_package_reader import (
    REFERENCE_PROFILE_V2,
    load_reference_package,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.temporal_evidence.access_models import (
    TemporalAccessContext,
    TemporalRetrievalState,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.temporal_evidence.corpus import (
    ASW_8_REFERENCE_WINDOW_END_SECONDS,
    ASW_8_REFERENCE_WINDOW_START_SECONDS,
    REFERENCE_WORLD_TIME_SECONDS,
    build_asw_8_reference_temporal_evidence_bundle,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.temporal_evidence.gateway import (
    TemporalEvidenceGateway,
)


def _context(world_time_seconds: int, branch: str = "branch-root") -> TemporalAccessContext:
    return TemporalAccessContext(
        run_id="run-asw-8",
        episode_id="episode-asw-8",
        world_instance_id="world-asw-8",
        world_branch_id=branch,
        world_state_id=f"state-{world_time_seconds}",
        world_commit_id=f"commit-{world_time_seconds}",
        world_sequence=1,
        world_time_seconds=world_time_seconds,
        actor_id="actor-1",
        actor_role="station-steward",
        agent_tenure_id="tenure-1",
        session_id="session-1",
        base_view_id="view-1",
        prior_information_set_id="information-1",
        tool_contract_id="pump-station.actor.v2",
        branch_ancestor_ids=(),
    )


def test_asw_8_builder_keeps_legacy_clock_constant_and_binds_v2_lineage() -> None:
    package = load_reference_package(profile_id=REFERENCE_PROFILE_V2)
    first = build_asw_8_reference_temporal_evidence_bundle(package, world_branch_id="branch-one")
    second = build_asw_8_reference_temporal_evidence_bundle(package, world_branch_id="branch-two")

    assert REFERENCE_WORLD_TIME_SECONDS == 7_200_000
    assert ASW_8_REFERENCE_WINDOW_START_SECONDS == 21_600
    assert ASW_8_REFERENCE_WINDOW_END_SECONDS == 226_800
    assert first.lineage.parent_profile_id == REFERENCE_PROFILE_V2
    assert first.content_sha256 != second.content_sha256
    assert first.corpus_manifest.content_sha256 == second.corpus_manifest.content_sha256
    c_note = next(item for item in first.versions if item.version_id == "pump-c-collateral-inspection-note.v1")
    assert c_note.applicable_component_ids == ("pump-c",)
    assert "CCR28H" in (c_note.content_text or "")


def test_exact_c_marker_is_hidden_at_peak_end_and_available_at_review_point() -> None:
    package = load_reference_package(profile_id=REFERENCE_PROFILE_V2)
    bundle = build_asw_8_reference_temporal_evidence_bundle(package, world_branch_id="branch-root")
    gateway = TemporalEvidenceGateway(bundle)
    state = TemporalRetrievalState(
        state_sequence=0,
        previous_state_id=None,
        reference_namespace_id="references-1",
        remaining_budget=bundle.capability.initial_budget,
        issued_references=(),
        access_result_ids=(),
        actor_event_ids=(),
        fetched_content_ids=(),
        unresolved_search_ids=(),
        installed_carrier_id=None,
    )

    before = gateway.search(
        request_id="search-before",
        query="CCR28H",
        scope="operations",
        limit=1,
        context=_context(93_600),
        state=state,
        resulting_information_set_id="information-before",
    )
    after = gateway.search(
        request_id="search-after",
        query="CCR28H",
        scope="operations",
        limit=1,
        context=_context(100_800),
        state=state,
        resulting_information_set_id="information-after",
    )

    assert before.result.references == ()
    assert tuple(item.version_id for item in after.result.references) == ("pump-c-collateral-inspection-note.v1",)
    fetched = gateway.fetch(
        request_id="fetch-after",
        reference=after.result.references[0].opaque_reference,
        context=_context(100_800),
        state=after.next_state,
        resulting_information_set_id="information-fetched",
    )
    assert fetched.result.fetched_content is not None
    assert "CCR28H" in fetched.result.fetched_content.content
