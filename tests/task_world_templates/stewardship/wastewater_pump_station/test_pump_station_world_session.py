# ABOUTME: Tests the pump-station session tools over the real durable world-run repository.
# ABOUTME: Covers typed actions, exact snapshot resume, actor projection, and independent replay.

from __future__ import annotations

import json
from pathlib import Path

from aec_bench.contracts.world_session import (
    WorldSessionExecutionKind,
    WorldSessionOpenMode,
    WorldSessionRequest,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_session import (
    PUMP_STATION_TASK_WORLD_ID,
    PUMP_STATION_TOOL_NAMES,
    PumpStationWorldSessionFactory,
)


def _start_request() -> WorldSessionRequest:
    return WorldSessionRequest(
        execution_kind=WorldSessionExecutionKind.STEWARDSHIP,
        open_mode=WorldSessionOpenMode.START,
        session_id="session-1",
        task_world_id=PUMP_STATION_TASK_WORLD_ID,
        agent_tenure_id="tenure-1",
        run_id="run-1",
        episode_id="episode-1",
        world_branch_id="branch-1",
    )


def test_session_exposes_closed_typed_tool_catalogue_and_replays_run(tmp_path: Path) -> None:
    factory = PumpStationWorldSessionFactory(tmp_path / "world")
    session = factory.open(_start_request())

    assert tuple(tool.name for tool in session.tool_specs) == PUMP_STATION_TOOL_NAMES
    assert tuple(tool.__name__ for tool in session.native_tools) == PUMP_STATION_TOOL_NAMES
    assert json.loads(session.observe_pump_station())["current_state"]["state_sequence"] == 0

    transition = json.loads(
        session.continue_operation(
            proposal_id="proposal-1",
            reason="Continue to the next declared event.",
        )
    )

    assert transition["status"] == "completed"
    assert transition["snapshot"]["sequence"] == 1
    assert session.verify().valid is True


def test_session_resumes_exact_selected_snapshot_under_fresh_tenure(tmp_path: Path) -> None:
    factory = PumpStationWorldSessionFactory(tmp_path / "world")
    first = factory.open(_start_request())
    first.continue_operation(
        proposal_id="proposal-1",
        reason="Continue to the next declared event.",
    )
    snapshot = first.result.snapshot

    resumed = factory.open(
        WorldSessionRequest(
            execution_kind=WorldSessionExecutionKind.STEWARDSHIP,
            open_mode=WorldSessionOpenMode.RESUME,
            session_id="session-2",
            task_world_id=PUMP_STATION_TASK_WORLD_ID,
            agent_tenure_id="tenure-2",
            run_id="run-1",
            episode_id="episode-1",
            world_branch_id="branch-1",
            start_snapshot=snapshot,
        )
    )

    assert resumed.result.snapshot == snapshot
    assert resumed.result.agent_tenure_id == "tenure-2"
    assert json.loads(resumed.observe_pump_station())["agent_tenure_id"] == "tenure-2"
    assert resumed.verify().valid is True


def test_session_tools_execute_complete_reference_stewardship_journey(tmp_path: Path) -> None:
    session = PumpStationWorldSessionFactory(tmp_path / "world").open(_start_request())
    reason = "Execute the deterministic reference stewardship journey."

    session.request_conditional_deferral("proposal-01", reason, "pump-a")
    session.transfer_duty("proposal-02", reason)
    session.request_inspection("proposal-03", reason, "pump-a")
    inspection_completed = json.loads(session.continue_operation("proposal-04", reason))
    inspection_id = next(
        item["evidence_id"]
        for item in inspection_completed["view"]["current_state"]["evidence"]
        if item["kind"] == "inspection"
    )
    session.continue_operation("proposal-05", reason)
    session.request_obstruction_clearance(
        "proposal-06",
        reason,
        "pump-a",
        inspection_id,
    )
    session.continue_operation("proposal-07", reason)
    checks_completed = json.loads(session.continue_operation("proposal-08", reason))
    functional_check_id = next(
        item["evidence_id"]
        for item in checks_completed["view"]["current_state"]["evidence"]
        if item["kind"] == "functional_checks"
    )
    returned = json.loads(
        session.request_provisional_return(
            "proposal-09",
            reason,
            "pump-a",
            functional_check_id,
        )
    )
    work_order_id = returned["view"]["current_state"]["work_orders"][0]["work_order_id"]
    session.request_provisional_closure("proposal-10", reason, work_order_id)
    session.request_post_maintenance_verification(
        "proposal-11",
        reason,
        "pump-a",
    )
    verified = json.loads(session.continue_operation("proposal-12", reason))

    assert verified["status"] == "completed"
    assert session.result.snapshot.sequence == 12
    assert session.verify().valid is True
