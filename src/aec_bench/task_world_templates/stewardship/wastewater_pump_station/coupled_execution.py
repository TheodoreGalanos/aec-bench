# ABOUTME: Executes the installed ASW-8 reference controller through actor v2 and temporal evidence tools.
# ABOUTME: Returns durable world evidence and one transport-neutral semantic outcome for parity checks.

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from aec_bench.contracts.world_interface import WorldActorBinding
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.actor_interface import (
    pump_station_actor_capabilities_v2,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_evaluation import (
    PumpStationSemanticOutcome,
    semantic_outcome,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_interface import (
    PumpStationCoupledLocalRequest,
    execute_coupled_local_request,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_run import (
    PumpStationCoupledRun,
    PumpStationCoupledRunRepository,
    create_coupled_run,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_runtime import (
    PUMP_STATION_OPERATIONS_REVIEW_VERSION,
    PumpStationOperationsBoundaryReviewRequest,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_work import (
    PumpStationBacklogStatus,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.reference_package_reader import (
    REFERENCE_PROFILE_V2,
    load_reference_package,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.temporal_evidence.access_models import (
    TemporalAccessContext,
    TemporalRetrievalState,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.temporal_evidence.corpus import (
    build_asw_8_reference_temporal_evidence_bundle,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.temporal_evidence.gateway import (
    TemporalEvidenceGateway,
)

PUMP_STATION_ASW_8_REFERENCE_CONTROLLER_ID = "pump-station-asw-8-reference-controller.v1"


@dataclass(frozen=True, slots=True)
class PumpStationReferenceControllerResult:
    """Complete direct or Harbor-neutral output of the fixed ASW-8 journey."""

    controller_id: str
    run: PumpStationCoupledRun
    temporal_access: tuple[tuple[str, str, tuple[str, ...]], ...]
    semantic_outcome: PumpStationSemanticOutcome


def _reason(request_id: str) -> str:
    return f"Complete {request_id} under the current visible service and work plan."


def _act(
    run: PumpStationCoupledRun,
    request_id: str,
    action_name: str,
    **arguments: object,
) -> PumpStationCoupledRun:
    return run.apply_actor(
        request_id=request_id,
        action_name=action_name,
        arguments={"reason": _reason(request_id), **arguments},
    )


def _continue_to(run: PumpStationCoupledRun, target: int) -> PumpStationCoupledRun:
    while run.state.calendar_seconds < target:
        run = _act(run, f"continue-{len(run.commands) + 1}", "continue_operation")
    if run.state.calendar_seconds != target:
        raise RuntimeError(f"reference controller passed target time {target}")
    return run


def _item_id(run: PumpStationCoupledRun, rule_id: str, target_id: str) -> str:
    matching = tuple(
        item.item_id
        for item in run.state.backlog
        if item.generation_rule_id == rule_id
        and item.target_id == target_id
        and item.status in {PumpStationBacklogStatus.OPEN, PumpStationBacklogStatus.PLANNED}
    )
    if len(matching) != 1:
        raise RuntimeError(f"reference work selection differs for {rule_id} and {target_id}")
    return matching[0]


def _review(
    run: PumpStationCoupledRun,
    *,
    review_id: str,
    kind: str,
    pump_id: str,
    restriction_id: str,
    evidence_id: str,
) -> PumpStationCoupledRun:
    return run.apply_review(
        PumpStationOperationsBoundaryReviewRequest(
            version=PUMP_STATION_OPERATIONS_REVIEW_VERSION,
            review_id=review_id,
            review_kind=kind,
            pump_id=pump_id,
            restriction_or_isolation_permit_id=restriction_id,
            accepted_evidence_id=evidence_id,
            requested_outcome="release",
            base_state_id=run.state.state_id,
            operations_authority_id="operations-controller",
            reason="Release only the matched boundary after the accepted evidence.",
        )
    )


def _temporal_context(run: PumpStationCoupledRun, *, tenure_id: str) -> TemporalAccessContext:
    return TemporalAccessContext(
        run_id=run.manifest.run_id,
        episode_id=run.manifest.episode_id,
        world_instance_id=run.manifest.run_id,
        world_branch_id=run.manifest.world_branch_id,
        world_state_id=run.state.state_id,
        world_commit_id=f"commit-{run.state.sequence}",
        world_sequence=run.state.sequence,
        world_time_seconds=run.state.calendar_seconds,
        actor_id="reference-controller",
        actor_role="station-steward",
        agent_tenure_id=tenure_id,
        session_id=f"session-{tenure_id}",
        base_view_id=f"view-{run.state.state_id}",
        prior_information_set_id=f"information-{run.state.state_id}",
        tool_contract_id="pump-station.actor.v2",
        branch_ancestor_ids=(),
    )


def execute_asw_8_reference_controller(
    *,
    run_id: str,
    world_branch_id: str,
) -> PumpStationReferenceControllerResult:
    """Execute the complete fixed Day 0 to Day 2 journey through closed tools."""
    package = load_reference_package(profile_id=REFERENCE_PROFILE_V2)
    bundle = build_asw_8_reference_temporal_evidence_bundle(
        package,
        world_branch_id=world_branch_id,
    )
    pump_station_actor_capabilities_v2(
        task_world_id="wastewater-pump-station-stewardship.v1",
        temporal_repository_verified=True,
    )
    gateway = TemporalEvidenceGateway(bundle)
    retrieval_state = TemporalRetrievalState(
        state_sequence=0,
        previous_state_id=None,
        reference_namespace_id=f"references-{world_branch_id}",
        remaining_budget=bundle.capability.initial_budget,
        issued_references=(),
        access_result_ids=(),
        actor_event_ids=(),
        fetched_content_ids=(),
        unresolved_search_ids=(),
        installed_carrier_id=None,
    )
    temporal_records: list[tuple[str, str, tuple[str, ...]]] = []
    run = create_coupled_run(run_id=run_id, world_branch_id=world_branch_id)
    run = _act(
        run,
        "a-verification",
        "request_post_maintenance_verification",
        pump_id="pump-a",
        backlog_item_id="backlog-a-verification-001",
    )
    run = _continue_to(run, 50_400)
    run = _review(
        run,
        review_id="operations-review-a-001",
        kind="post_verification_restriction",
        pump_id="pump-a",
        restriction_id="restriction-a-run-in-001",
        evidence_id="evidence-pump-a-verification-pass-001",
    )
    run = _continue_to(run, 64_800)
    run = _act(
        run,
        "assign-a-c",
        "request_duty_assignment",
        ordered_pump_ids=["pump-a", "pump-c"],
    )
    run = _continue_to(run, 93_600)
    run = run.handover(
        handover_id="handover-peak-end",
        from_tenure_id="tenure-day-0",
        to_tenure_id="tenure-day-1",
    )
    before = gateway.search(
        request_id="search-ccr28h-before",
        query="CCR28H",
        scope="operations",
        limit=1,
        context=_temporal_context(run, tenure_id="tenure-day-1"),
        state=retrieval_state,
        resulting_information_set_id="information-ccr28h-before",
    )
    retrieval_state = before.next_state
    temporal_records.append(
        (
            "search_evidence",
            before.result.public_status.value,
            tuple(item.version_id for item in before.result.references),
        )
    )
    run = _continue_to(run, 100_800)
    after = gateway.search(
        request_id="search-ccr28h-after",
        query="CCR28H",
        scope="operations",
        limit=1,
        context=_temporal_context(run, tenure_id="tenure-day-1"),
        state=retrieval_state,
        resulting_information_set_id="information-ccr28h-after",
    )
    retrieval_state = after.next_state
    temporal_records.append(
        (
            "search_evidence",
            after.result.public_status.value,
            tuple(item.version_id for item in after.result.references),
        )
    )
    fetched = gateway.fetch(
        request_id="fetch-ccr28h",
        reference=after.result.references[0].opaque_reference,
        context=_temporal_context(run, tenure_id="tenure-day-1"),
        state=retrieval_state,
        resulting_information_set_id="information-ccr28h-fetch",
    )
    retrieval_state = fetched.next_state
    temporal_records.append(
        (
            "fetch_evidence",
            fetched.result.public_status.value,
            (fetched.result.fetched_content.version_id if fetched.result.fetched_content is not None else "",),
        )
    )
    run = _continue_to(run, 108_000)
    run = _act(
        run,
        "b-clearance",
        "request_obstruction_clearance",
        pump_id="pump-b",
        backlog_item_id="backlog-b-clearance-001",
        inspection_evidence_id="initial-b-inspection-accepted",
    )
    run = _continue_to(run, 122_400)
    run = _act(
        run,
        "b-functional",
        "request_functional_check",
        pump_id="pump-b",
        backlog_item_id=_item_id(run, "WG-03", "pump-b"),
    )
    run = _continue_to(run, 126_000)
    run = _act(
        run,
        "b-provisional-return",
        "request_provisional_return",
        pump_id="pump-b",
        functional_check_evidence_id="evidence-b-functional-check-pass-001",
    )
    run = _act(
        run,
        "b-provisional-closure",
        "request_provisional_closure",
        work_order_id="work-order-b-001",
    )
    run = _act(
        run,
        "b-verification",
        "request_post_maintenance_verification",
        pump_id="pump-b",
        backlog_item_id=_item_id(run, "WG-04", "pump-b"),
    )
    run = _continue_to(run, 154_800)
    run = _review(
        run,
        review_id="operations-review-b-001",
        kind="post_verification_restriction",
        pump_id="pump-b",
        restriction_id="restriction-pump-b-run-in-001",
        evidence_id="evidence-pump-b-verification-pass-001",
    )
    run = _continue_to(run, 194_400)
    run = _act(
        run,
        "assign-a-b",
        "request_duty_assignment",
        ordered_pump_ids=["pump-a", "pump-b"],
    )
    run = _act(
        run,
        "c-inspection",
        "request_inspection",
        pump_id="pump-c",
        backlog_item_id=_item_id(run, "WG-07", "pump-c"),
    )
    run = _continue_to(run, 223_200)
    run = _review(
        run,
        review_id="operations-review-c-001",
        kind="post_inspection_isolation",
        pump_id="pump-c",
        restriction_id="isolation-pump-c-c-inspection",
        evidence_id="evidence-c-inspection-no-finding-001",
    )
    access = tuple(temporal_records)
    return PumpStationReferenceControllerResult(
        controller_id=PUMP_STATION_ASW_8_REFERENCE_CONTROLLER_ID,
        run=run,
        temporal_access=access,
        semantic_outcome=semantic_outcome(run, temporal_access=access),
    )


def execute_asw_8_reference_controller_through_interface(
    *,
    run_root: Path,
    run_id: str,
    world_branch_id: str,
) -> PumpStationReferenceControllerResult:
    """Execute the fixed journey through the installed actor and host-control surface."""
    expected = execute_asw_8_reference_controller(
        run_id=run_id,
        world_branch_id=world_branch_id,
    )
    execute_coupled_local_request(
        run_root=run_root,
        request=PumpStationCoupledLocalRequest(
            operation="start",
            run_id=run_id,
            world_branch_id=world_branch_id,
        ),
    )
    access: list[tuple[str, str, tuple[str, ...]]] = []
    after_search_complete = False
    current_tenure_id = "tenure-day-0"
    for command in expected.run.commands:
        arguments = command.arguments
        if "ordered_pump_ids" in arguments:
            arguments["ordered_pump_ids"] = tuple(arguments["ordered_pump_ids"])
        if command.kind == "actor":
            binding = _interface_observation_binding(
                run_root=run_root,
                agent_tenure_id=current_tenure_id,
            )
            execute_coupled_local_request(
                run_root=run_root,
                request=PumpStationCoupledLocalRequest(
                    operation="actor_action",
                    request_id=command.request_id,
                    action_name=command.action_name,
                    arguments=arguments,
                    binding=binding,
                ),
            )
        elif command.kind == "operations_review":
            review = PumpStationOperationsBoundaryReviewRequest(**arguments)
            execute_coupled_local_request(
                run_root=run_root,
                request=PumpStationCoupledLocalRequest(
                    operation="operations_review",
                    operations_review=review,
                ),
                host_authority_id=review.operations_authority_id,
            )
        elif command.kind == "handover":
            execute_coupled_local_request(
                run_root=run_root,
                request=PumpStationCoupledLocalRequest(
                    operation="handover",
                    request_id=command.request_id,
                    from_agent_tenure_id=str(arguments["from_tenure_id"]),
                    to_agent_tenure_id=str(arguments["to_tenure_id"]),
                ),
            )
            current_tenure_id = str(arguments["to_tenure_id"])
        else:
            raise RuntimeError(f"reference controller contains unsupported command kind {command.kind}")
        current = PumpStationCoupledRunRepository(run_root).open()
        if command.kind == "handover":
            before = _interface_temporal_access(
                run_root=run_root,
                request_id="search-ccr28h-before",
                action_name="search_evidence",
                arguments={"query": "CCR28H", "scope": "operations", "limit": 1},
            )
            access.append(_semantic_temporal_access("search_evidence", before))
        if current.state.calendar_seconds == 100_800 and not after_search_complete:
            after = _interface_temporal_access(
                run_root=run_root,
                request_id="search-ccr28h-after",
                action_name="search_evidence",
                arguments={"query": "CCR28H", "scope": "operations", "limit": 1},
            )
            access.append(_semantic_temporal_access("search_evidence", after))
            references = cast(list[dict[str, Any]], after["references"])
            fetched = _interface_temporal_access(
                run_root=run_root,
                request_id="fetch-ccr28h",
                action_name="fetch_evidence",
                arguments={"reference": str(references[0]["opaque_reference"])},
            )
            access.append(_semantic_temporal_access("fetch_evidence", fetched))
            after_search_complete = True
    run = PumpStationCoupledRunRepository(run_root).open()
    temporal_access = tuple(access)
    durable_semantics = (run.manifest, run.state, run.commands, run.receipts)
    expected_semantics = (
        expected.run.manifest,
        expected.run.state,
        expected.run.commands,
        expected.run.receipts,
    )
    proposal_semantics = tuple((type(proposal).__name__, proposal.context.proposal_id) for proposal in run.proposals)
    expected_proposal_semantics = tuple(
        (type(proposal).__name__, proposal.context.proposal_id) for proposal in expected.run.proposals
    )
    if (
        durable_semantics != expected_semantics
        or proposal_semantics != expected_proposal_semantics
        or temporal_access != expected.temporal_access
    ):
        raise RuntimeError("installed reference journey differs from the pure controller")
    return PumpStationReferenceControllerResult(
        controller_id=PUMP_STATION_ASW_8_REFERENCE_CONTROLLER_ID,
        run=run,
        temporal_access=temporal_access,
        semantic_outcome=semantic_outcome(run, temporal_access=temporal_access),
    )


def _interface_temporal_access(
    *,
    run_root: Path,
    request_id: str,
    action_name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    binding = _interface_observation_binding(
        run_root=run_root,
        agent_tenure_id="tenure-day-1",
    )
    response = execute_coupled_local_request(
        run_root=run_root,
        request=PumpStationCoupledLocalRequest(
            operation="actor_action",
            request_id=request_id,
            action_name=action_name,
            arguments=arguments,
            binding=binding,
        ),
    )
    return cast(dict[str, Any], response["payload"])


def _interface_observation_binding(
    *,
    run_root: Path,
    agent_tenure_id: str,
) -> WorldActorBinding:
    response = execute_coupled_local_request(
        run_root=run_root,
        request=PumpStationCoupledLocalRequest(
            operation="observe",
            agent_tenure_id=agent_tenure_id,
            session_id=f"session-{agent_tenure_id}",
        ),
    )
    payload = cast(dict[str, Any], response["payload"])
    return WorldActorBinding.model_validate(payload["binding"])


def _semantic_temporal_access(
    action_name: str,
    payload: dict[str, Any],
) -> tuple[str, str, tuple[str, ...]]:
    references = cast(list[dict[str, Any]], payload["references"])
    version_ids = tuple(str(item["version_id"]) for item in references)
    fetched = payload.get("fetched_content")
    if isinstance(fetched, dict):
        version_ids = (str(fetched["version_id"]),)
    return action_name, str(payload["public_status"]), version_ids
