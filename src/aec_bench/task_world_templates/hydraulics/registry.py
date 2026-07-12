# ABOUTME: Registry for public deterministic hydraulic mini-world source definitions.
# ABOUTME: Gives PR19 a stable world-id lookup without coupling to lifecycle execution.

from __future__ import annotations

from collections.abc import Callable

from aec_bench.task_world_templates.hydraulics.contracts import HydraulicSourceState
from aec_bench.task_world_templates.hydraulics.worlds.ssc03_detention_network import (
    WORLD_ID as SSC03_WORLD_ID,
)
from aec_bench.task_world_templates.hydraulics.worlds.ssc03_detention_network import (
    build_source_state as build_ssc03_source_state,
)

_WORLD_BUILDERS: dict[str, Callable[[], HydraulicSourceState]] = {
    SSC03_WORLD_ID: build_ssc03_source_state,
}


def list_hydraulic_world_ids() -> tuple[str, ...]:
    """Return registered public hydraulic world IDs in stable order."""
    return tuple(sorted(_WORLD_BUILDERS))


def get_hydraulic_source_state(world_id: str) -> HydraulicSourceState:
    """Return a fresh validated source state for one registered world."""
    try:
        builder = _WORLD_BUILDERS[world_id]
    except KeyError as exc:
        known = ", ".join(list_hydraulic_world_ids())
        raise KeyError(f"unknown hydraulic world {world_id!r}; expected one of: {known}") from exc
    return builder()
