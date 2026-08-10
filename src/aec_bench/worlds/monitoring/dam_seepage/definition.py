# ABOUTME: Registers the dam seepage world and validates its content-pinned synthetic profile.
# ABOUTME: Keeps scenario loading separate from task transitions and provider integrations.

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from aec_bench.contracts.interactive_world import InteractiveWorldProfileRef, WorldBuildRef
from aec_bench.worlds.monitoring.dam_seepage.world import (
    DAM_SEEPAGE_TASK_WORLD_ID,
    SeepageScenario,
    SeepageState,
    initial_state,
)
from aec_bench.worlds.runtime.definition import (
    InteractiveWorldDefinition,
    LoadedInteractiveWorldProfile,
    source_tree_world_build,
)

_SCENARIO_PATH = Path(__file__).with_name("rising-seepage.json")


@dataclass(frozen=True, slots=True)
class DamSeepageProfile:
    """Validated task scenario and its exact opening state."""

    scenario: SeepageScenario
    opening_state: SeepageState


def _scenario_bytes() -> bytes:
    return _SCENARIO_PATH.read_bytes()


@cache
def _scenario() -> SeepageScenario:
    return SeepageScenario.model_validate_json(_scenario_bytes())


@cache
def _profile_ref() -> InteractiveWorldProfileRef:
    scenario = _scenario()
    return InteractiveWorldProfileRef(
        task_world_id=scenario.task_world_id,
        profile_id=scenario.profile_id,
        profile_content_sha256=hashlib.sha256(_scenario_bytes()).hexdigest(),
    )


def _load_profile(reference: InteractiveWorldProfileRef) -> LoadedInteractiveWorldProfile:
    current = _profile_ref()
    if reference != current:
        raise ValueError("dam seepage profile content differs")
    scenario = _scenario()
    return LoadedInteractiveWorldProfile(
        reference=reference,
        value=DamSeepageProfile(scenario=scenario, opening_state=initial_state(scenario)),
    )


@cache
def _world_build() -> WorldBuildRef:
    source_root = Path(__file__).resolve().parents[3]
    return source_tree_world_build(
        task_world_id=DAM_SEEPAGE_TASK_WORLD_ID,
        entry_point="aec_bench.worlds.monitoring.dam_seepage.definition:dam_seepage_world_definition",
        roots=(
            Path(__file__).resolve().parent,
            source_root / "contracts" / "interactive_world.py",
            source_root / "contracts" / "continual_world.py",
            source_root / "contracts" / "harness_kernel.py",
            source_root / "contracts" / "validators.py",
            source_root / "worlds" / "runtime" / "definition.py",
            source_root / "worlds" / "runtime" / "episode.py",
            source_root / "worlds" / "runtime" / "world_logic.py",
        ),
    )


@cache
def dam_seepage_world_definition() -> InteractiveWorldDefinition:
    """Return the current dam seepage build and synthetic monitoring profile."""
    profile = _profile_ref()
    return InteractiveWorldDefinition(
        build=_world_build(),
        profiles=(profile,),
        profile_loader=_load_profile,
    )
