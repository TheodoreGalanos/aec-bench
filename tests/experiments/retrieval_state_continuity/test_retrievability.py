# ABOUTME: Verifies the frozen study query routes against the real temporal gateway.
# ABOUTME: Proves delayed material evidence is hidden, then searchable and fetchable.

from __future__ import annotations

from aec_bench.contracts.harness_kernel import canonical_content_sha256
from aec_bench.experiments.retrieval_state_continuity import StudyManifest, build_provider_free_manifest
from aec_bench.task_world_templates.stewardship.wastewater_pump_station import load_reference_package
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.temporal_evidence import (
    RetrievalBudgetVector,
    TemporalAccessContext,
    TemporalEvidenceAccessStatus,
    TemporalEvidenceGateway,
    TemporalRetrievalState,
    build_reference_temporal_evidence_bundle,
)


def test_frozen_query_routes_hide_then_retrieve_and_fetch_material_evidence() -> None:
    manifest = build_provider_free_manifest()
    bundle = build_reference_temporal_evidence_bundle(
        load_reference_package(),
        world_branch_id="study-main",
    )
    gateway = TemporalEvidenceGateway(bundle)

    for route_index, query in enumerate(manifest.development_query_routes, start=1):
        before = gateway.search(
            request_id=f"before-{route_index}",
            query=query,
            scope="condition",
            limit=manifest.budget.maximum_references_per_result,
            context=_context(manifest.pre_handover_world_time_seconds),
            state=_state(manifest),
            resulting_information_set_id=f"before-information-set-{route_index}",
        )
        after = gateway.search(
            request_id=f"after-{route_index}",
            query=query,
            scope="condition",
            limit=manifest.budget.maximum_references_per_result,
            context=_context(manifest.evidence_available_at_seconds),
            state=_state(manifest),
            resulting_information_set_id=f"after-information-set-{route_index}",
        )

        assert before.result.public_status is TemporalEvidenceAccessStatus.NO_ACCESSIBLE_RESULT
        assert after.result.public_status is TemporalEvidenceAccessStatus.OK
        material = next(
            item for item in after.result.references if item.version_id == manifest.material_evidence_version_id
        )
        fetched = gateway.fetch(
            request_id=f"fetch-{route_index}",
            reference=material.opaque_reference,
            context=_context(manifest.evidence_available_at_seconds),
            state=after.next_state,
            resulting_information_set_id=f"fetch-information-set-{route_index}",
        )
        assert fetched.result.public_status is TemporalEvidenceAccessStatus.OK
        assert fetched.result.fetched_content is not None
        assert fetched.result.fetched_content.version_id == manifest.material_evidence_version_id
        assert fetched.receipt.budget_before.calls == 2
        assert fetched.receipt.budget_after.calls == 1


def _context(world_time_seconds: int) -> TemporalAccessContext:
    return TemporalAccessContext(
        run_id="retrieval-state-study-run",
        episode_id="retrieval-state-study-episode",
        world_instance_id="station-001",
        world_branch_id="study-main",
        world_state_id="retrieval-state-study-state",
        world_commit_id="retrieval-state-study-commit",
        world_sequence=1,
        world_time_seconds=world_time_seconds,
        actor_id="station-steward",
        actor_role="station-steward",
        agent_tenure_id="retrieval-state-study-tenure",
        session_id="retrieval-state-study-session",
        base_view_id="retrieval-state-study-view",
        prior_information_set_id="retrieval-state-study-information-set",
        tool_contract_id="pump-station-temporal-tools.v1",
        branch_ancestor_ids=(),
    )


def _state(manifest: StudyManifest) -> TemporalRetrievalState:
    budget = manifest.budget
    return TemporalRetrievalState(
        state_sequence=0,
        previous_state_id=None,
        reference_namespace_id=canonical_content_sha256(
            {"session": "retrieval-state-study-session", "tenure": "retrieval-state-study-tenure"},
        ),
        remaining_budget=RetrievalBudgetVector(
            calls=budget.maximum_search_calls + budget.maximum_fetch_calls,
            returned_references=budget.maximum_search_calls * budget.maximum_references_per_result,
            visible_bytes=budget.maximum_visible_bytes,
            visible_tokens=budget.maximum_visible_tokens,
            turns=budget.maximum_agent_turns,
            simulated_duration_seconds=budget.simulated_retrieval_duration_seconds,
            provider_spend_microusd=budget.external_retrieval_provider_spend_microusd,
        ),
        issued_references=(),
        access_result_ids=(),
        actor_event_ids=(),
        fetched_content_ids=(),
        unresolved_search_ids=(),
        installed_carrier_id=None,
    )
