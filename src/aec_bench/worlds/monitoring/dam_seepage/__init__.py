# ABOUTME: Exposes the dam seepage world owner and its direct task functions.
# ABOUTME: Keeps provider, persistence, emergency authority, and evaluation orchestration outside the task.

from aec_bench.worlds.monitoring.dam_seepage.definition import (
    DamSeepageProfile,
    dam_seepage_world_definition,
)
from aec_bench.worlds.monitoring.dam_seepage.world import (
    DAM_SEEPAGE_TASK_WORLD_ID,
    SeepageAction,
    SeepageScenario,
    SeepageState,
    available_actions,
    evaluate,
    initial_state,
    observe,
    requires_engineering_review,
    transition,
)
from aec_bench.worlds.runtime.definition import InteractiveWorldOwnerDescriptor

__all__ = [
    "DAM_SEEPAGE_TASK_WORLD_ID",
    "DamSeepageProfile",
    "WORLD_DESCRIPTOR",
    "SeepageAction",
    "SeepageScenario",
    "SeepageState",
    "available_actions",
    "dam_seepage_world_definition",
    "evaluate",
    "initial_state",
    "observe",
    "requires_engineering_review",
    "transition",
]

WORLD_DESCRIPTOR = InteractiveWorldOwnerDescriptor(
    task_world_id="dam-seepage-monitoring",
    entry_point="aec_bench.worlds.monitoring.dam_seepage.definition:dam_seepage_world_definition",
)
