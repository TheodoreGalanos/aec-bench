# ABOUTME: Tests the bounded ASW-8 agent session over the same closed installed actor tools.
# ABOUTME: Proves the model surface contains projection v5 and no latent physical condition.

from __future__ import annotations

import json
from pathlib import Path

from aec_bench.task_world_templates.stewardship.wastewater_pump_station.actor_interface import (
    PUMP_STATION_ACTOR_ACTION_NAMES_V2,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_agent import (
    PumpStationCoupledAgentSession,
)


def test_coupled_agent_session_uses_closed_tools_and_natural_reasons(tmp_path: Path) -> None:
    session = PumpStationCoupledAgentSession.start(
        run_root=tmp_path / "run",
        run_id="agent-session-run",
        world_branch_id="branch-agent-session",
        agent_tenure_id="agent-tenure-001",
        session_id="agent-session-001",
    )

    assert tuple(spec.name for spec in session.tool_specs) == (
        "observe_pump_station",
        *PUMP_STATION_ACTOR_ACTION_NAMES_V2,
    )
    observation = json.loads(session.observe_pump_station())
    serialized = json.dumps(observation, sort_keys=True)
    view = observation["payload"]["view"]
    assert view["projection_policy_id"] == "pump-station-current-state.v5"
    boundaries = {item["pump_id"]: item for item in view["pump_boundaries"]}
    availability = {item["pump_id"]: item for item in view["pump_availability"]}
    assert boundaries["pump-a"]["mode"] == "run_in_service"
    assert availability["pump-a"]["run_eligible"] is True
    assert availability["pump-a"]["test_eligible"] is False
    assert availability["pump-a"]["assured_for_outage_planning"] is False
    assert availability["pump-a"]["source_restriction_ids"] == ["restriction-a-run-in-001"]
    assert availability["pump-a"]["decision_role"] == "operations-controller"
    assert availability["pump-a"]["closure_rule"] == "accepted evidence and Operations boundary review"
    assert '"obstruction":' not in serialized
    assert '"clearance_loss":' not in serialized

    search = json.loads(
        session.search_evidence(
            request_id="agent-search-001",
            query="controlled test permit",
            scope="operations",
            limit=1,
        )
    )
    assert search["payload"]["public_status"] == "OK"
    transition = json.loads(
        session.continue_operation(
            request_id="agent-continue-001",
            reason=(
                "Continue to the next declared event because the current assignment covers "
                "the visible service requirement."
            ),
        )
    )
    assert transition["sequence"] == 1
