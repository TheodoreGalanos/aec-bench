# ABOUTME: Exercises the provider-neutral host seam against the real pump-station session factory.
# ABOUTME: Proves lifecycle sessions do not receive stewardship tools when the capability is absent.

from __future__ import annotations

import json
from pathlib import Path

from aec_bench.contracts.world_session import (
    WorldSessionExecutionKind,
    WorldSessionOpenMode,
    WorldSessionRequest,
)
from aec_bench.harness.world_session import open_world_session
from aec_bench.meta_harness.evidence_lifecycle_local import build_lifecycle_tool_schema
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_session import (
    PUMP_STATION_TASK_WORLD_ID,
    PUMP_STATION_TOOL_NAMES,
    PumpStationWorldSessionFactory,
)


def test_host_opens_real_provider_neutral_pump_station_session(tmp_path: Path) -> None:
    request = WorldSessionRequest(
        execution_kind=WorldSessionExecutionKind.STEWARDSHIP,
        open_mode=WorldSessionOpenMode.START,
        session_id="session-1",
        task_world_id=PUMP_STATION_TASK_WORLD_ID,
        agent_tenure_id="tenure-1",
        run_id="run-1",
        episode_id="episode-1",
        world_branch_id="branch-1",
    )

    session = open_world_session(
        request,
        PumpStationWorldSessionFactory(tmp_path / "world"),
    )
    response = json.loads(
        session.continue_operation(
            proposal_id="proposal-1",
            reason="Continue to the next declared event.",
        )
    )

    assert session.result.execution_kind is WorldSessionExecutionKind.STEWARDSHIP
    assert session.result.snapshot.sequence == 1
    assert response["status"] == "completed"
    assert response["snapshot"]["sequence"] == 1


def test_lifecycle_tool_schema_excludes_stewardship_tools_without_capability() -> None:
    lifecycle_tools = build_lifecycle_tool_schema(
        "persistent_context",
        supports_evidence_requests=False,
        supports_lifecycle_operations=False,
    )

    lifecycle_tool_names = {item["name"] for item in lifecycle_tools}
    assert lifecycle_tool_names.isdisjoint(PUMP_STATION_TOOL_NAMES)
