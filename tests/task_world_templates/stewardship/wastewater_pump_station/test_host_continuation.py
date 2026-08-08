# ABOUTME: Proves pump-owned host continuation selects only exact eligible Operations reviews.
# ABOUTME: Keeps runtime completion separate from Prime session end and task evaluation.

from __future__ import annotations

from pathlib import Path
from typing import cast

from pydantic import JsonValue

from aec_bench.contracts.world_interface import WorldActorActionRequest
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.episode_runtime import (
    PumpStationEpisodeHost,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.host_continuation import (
    PUMP_STATION_OPERATIONS_AUTHORITY_ID,
    PumpStationJourneyStatus,
    pump_station_journey_status,
    resolve_pump_station_host_continuation,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.reference_controller import (
    run_pump_station_reference_controller,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_models import (
    PumpStationOperationsBoundaryReviewRequest,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_control import (
    PumpStationWorldControl,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run import (
    PumpStationWorldRun,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_repository import (
    PumpStationWorldRunRepository,
)


def _act(host: PumpStationEpisodeHost, request_id: str, action_name: str, **arguments: object) -> None:
    observation = host.observe()
    result = host.invoke(
        WorldActorActionRequest(
            request_id=request_id,
            decision_id=observation.decision_id,
            action_name=action_name,
            arguments=cast(
                dict[str, JsonValue],
                {"reason": f"Complete {request_id} under the visible service plan.", **arguments},
            ),
        )
    )
    assert result.status == "applied"


def _continue_to(host: PumpStationEpisodeHost, run: PumpStationWorldRun, target: int) -> None:
    while run.state.calendar_seconds < target:
        _act(host, f"continue-{run.snapshot().sequence + 1}", "continue_operation")
    assert run.state.calendar_seconds == target


def test_host_continuation_releases_only_a_matching_accepted_verification(tmp_path: Path) -> None:
    repository_root = tmp_path / "world"
    run = PumpStationWorldRun.create_reference_system(
        repository=PumpStationWorldRunRepository(repository_root),
        run_id="host-continuation-run",
        episode_id="host-continuation-episode",
        world_branch_id="host-continuation-branch",
    )
    host = PumpStationEpisodeHost(repository_root)

    opening = resolve_pump_station_host_continuation(run)
    assert opening.status is PumpStationJourneyStatus.ACTIVE
    assert opening.control_request is None
    assert "restriction-b-isolated-001" in run.state.active_restriction_ids

    _act(
        host,
        "a-verification",
        "request_post_maintenance_verification",
        pump_id="pump-a",
        backlog_item_id="backlog-a-verification-001",
    )
    assert resolve_pump_station_host_continuation(run).control_request is None
    _continue_to(host, run, 50_400)

    first = resolve_pump_station_host_continuation(run)
    retry = resolve_pump_station_host_continuation(run)
    assert first == retry
    assert first.status is PumpStationJourneyStatus.ACTIVE
    assert first.control_request is not None
    assert first.control_request.authority_id == PUMP_STATION_OPERATIONS_AUTHORITY_ID
    assert first.control_request.base_state_id == run.state.state_id
    assert first.control_request.based_on_sequence == run.snapshot().sequence
    review = first.control_request.control
    assert isinstance(review, PumpStationOperationsBoundaryReviewRequest)
    assert review.pump_id == "pump-a"
    assert review.accepted_evidence_id == "evidence-pump-a-verification-pass-001"
    assert review.restriction_or_isolation_permit_id == "restriction-a-run-in-001"

    control = PumpStationWorldControl(
        repository_root,
        authorised_principal_ids=(PUMP_STATION_OPERATIONS_AUTHORITY_ID,),
    )
    result = control.execute(first.control_request)
    exact_retry = control.execute(first.control_request)
    assert exact_retry == result
    assert result.receipt.state_changed
    assert result.receipt.result_snapshot is not None
    assert result.receipt.result_snapshot.state_id == run.state.state_id
    assert "restriction-a-run-in-001" not in run.state.active_restriction_ids
    assert resolve_pump_station_host_continuation(run).control_request is None


def test_declared_reference_terminal_state_is_completed_without_using_evaluation(tmp_path: Path) -> None:
    completed = run_pump_station_reference_controller(
        tmp_path / "world",
        run_id="completed-run",
        episode_id="completed-episode",
        world_branch_id="completed-branch",
    )

    assert pump_station_journey_status(completed.run.state) is PumpStationJourneyStatus.COMPLETED
    decision = resolve_pump_station_host_continuation(completed.run)
    assert decision.status is PumpStationJourneyStatus.COMPLETED
    assert decision.control_request is None
