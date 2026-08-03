# ABOUTME: Composes the public continual-world catalogue from real task-owned definitions.
# ABOUTME: Keeps concrete pump and hydraulic imports outside the task-neutral core package.

from __future__ import annotations

from functools import cache

from aec_bench.task_world_templates.continual.catalogue import ContinualWorldCatalogue
from aec_bench.task_world_templates.lifecycles.ssc03_hydraulic_continual_definition import (
    ssc03_hydraulic_continual_world_definition,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.continual_definition import (
    pump_station_continual_world_definition,
)


@cache
def default_continual_world_catalogue() -> ContinualWorldCatalogue:
    """Return the stable public catalogue with both real contract consumers."""
    return ContinualWorldCatalogue(
        definitions=(
            pump_station_continual_world_definition(),
            ssc03_hydraulic_continual_world_definition(),
        )
    )
