# ABOUTME: Exposes the pump-station world owner and its installed actor runtime.
# ABOUTME: Leaves task models, persistence details, and reference-package helpers with their owners.

from aec_bench.worlds.runtime.definition import InteractiveWorldOwnerDescriptor
from aec_bench.worlds.stewardship.wastewater_pump_station.actor_interface import (
    PUMP_STATION_ACTOR_ACTION_NAMES,
    PUMP_STATION_ACTOR_WORKSPACE_TOOL_ID,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.episode_runtime import (
    PUMP_STATION_TASK_WORLD_ID,
    PumpStationEpisodeHost,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.reference_package_reader import (
    load_reference_package,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run import (
    PumpStationWorldRun,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run_models import (
    PumpStationWorldRunError,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run_repository import (
    PumpStationWorldRunRepository,
)

__all__ = [
    "PUMP_STATION_ACTOR_ACTION_NAMES",
    "PUMP_STATION_ACTOR_WORKSPACE_TOOL_ID",
    "WORLD_DESCRIPTOR",
    "PUMP_STATION_TASK_WORLD_ID",
    "PumpStationEpisodeHost",
    "PumpStationWorldRun",
    "PumpStationWorldRunError",
    "PumpStationWorldRunRepository",
    "load_reference_package",
]

WORLD_DESCRIPTOR = InteractiveWorldOwnerDescriptor(
    task_world_id="wastewater-pump-station-stewardship.v1",
    entry_point=(
        "aec_bench.worlds.stewardship.wastewater_pump_station.continual_definition:"
        "pump_station_continual_world_definition"
    ),
)
