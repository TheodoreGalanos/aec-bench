# ABOUTME: Builds the shared pump-station session request used by Prime harness tests.
# ABOUTME: Avoids test modules importing private helpers from each other.

from aec_bench.contracts.world_session import (
    WorldSessionExecutionKind,
    WorldSessionOpenMode,
    WorldSessionRequest,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.episode_runtime import (
    PUMP_STATION_TASK_WORLD_ID,
)


def pump_station_prime_session_request() -> WorldSessionRequest:
    return WorldSessionRequest(
        execution_kind=WorldSessionExecutionKind.STEWARDSHIP,
        open_mode=WorldSessionOpenMode.START,
        session_id="prime-session",
        task_world_id=PUMP_STATION_TASK_WORLD_ID,
        agent_tenure_id="prime-composite-actor",
        run_id="prime-run",
        episode_id="prime-episode",
        world_branch_id="prime-branch",
    )
