# ABOUTME: Registers the dam seepage world and validates its content-pinned synthetic profiles.
# ABOUTME: Keeps scenario loading separate from task transitions and provider integrations.

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from uuid import UUID

from aec_bench.contracts.identity import EntityIdentity, EntityKey, MemberIdentity
from aec_bench.contracts.interactive_world import InteractiveWorldProfileRef, WorldBuildRef
from aec_bench.contracts.task_definition import Difficulty, Lifecycle, Visibility
from aec_bench.worlds.monitoring.dam_seepage.variants import dam_seepage_profile_variants
from aec_bench.worlds.monitoring.dam_seepage.world import (
    DAM_SEEPAGE_TASK_WORLD_ID,
    SeepageScenario,
    SeepageState,
    initial_state,
)
from aec_bench.worlds.runtime.definition import (
    InteractiveWorldDefinition,
    InteractiveWorldProfileMetadata,
    LoadedInteractiveWorldProfile,
    source_tree_world_build,
)

_BASE_SCENARIO_PATH = Path(__file__).with_name("rising-seepage.json")
_BASE_PROFILE_ID = "synthetic-rising-seepage"
_WORLD_IDENTITY = EntityIdentity(
    id=UUID("01a056f1-af83-7516-90f6-ceddb36390bd"),
    key=EntityKey("monitoring/dam-seepage"),
    version=1,
)
_PROFILE_IDENTITIES = {
    _BASE_PROFILE_ID: MemberIdentity(
        id=UUID("01a056f1-af83-7971-a160-8974515e3464"),
        key=EntityKey(f"{_WORLD_IDENTITY.key}/{_BASE_PROFILE_ID}"),
        version=1,
        parent_id=_WORLD_IDENTITY.id,
        registration_id=_BASE_PROFILE_ID,
    ),
    "reliable-routine-surveillance": MemberIdentity(
        id=UUID("01a056f1-af83-7ab8-b9e8-172a45b6a385"),
        key=EntityKey(f"{_WORLD_IDENTITY.key}/reliable-routine-surveillance"),
        version=1,
        parent_id=_WORLD_IDENTITY.id,
        registration_id="reliable-routine-surveillance",
    ),
    "unreliable-instrument-escalation": MemberIdentity(
        id=UUID("01a056f1-af83-7809-a226-ef872a3d8369"),
        key=EntityKey(f"{_WORLD_IDENTITY.key}/unreliable-instrument-escalation"),
        version=1,
        parent_id=_WORLD_IDENTITY.id,
        registration_id="unreliable-instrument-escalation",
    ),
    "unreliable-instrument-surface-transfer": MemberIdentity(
        id=UUID("01a056f1-af83-7f7f-9b90-754696fbe511"),
        key=EntityKey(f"{_WORLD_IDENTITY.key}/unreliable-instrument-surface-transfer"),
        version=1,
        parent_id=_WORLD_IDENTITY.id,
        registration_id="unreliable-instrument-surface-transfer",
    ),
}

for _profile_id, _identity in (
    ("investigation-routine", "01a056f1-af83-7100-8000-000000000001"),
    ("investigation-fault", "01a056f1-af83-7100-8000-000000000002"),
    ("investigation-urgent-fault", "01a056f1-af83-7100-8000-000000000003"),
):
    _PROFILE_IDENTITIES[_profile_id] = MemberIdentity(
        id=UUID(_identity),
        key=EntityKey(f"{_WORLD_IDENTITY.key}/{_profile_id}"),
        version=1,
        parent_id=_WORLD_IDENTITY.id,
        registration_id=_profile_id,
    )


@dataclass(frozen=True, slots=True)
class DamSeepageProfile:
    """Validated task scenario and its exact opening state."""

    scenario: SeepageScenario
    opening_state: SeepageState


@dataclass(frozen=True, slots=True)
class _RegisteredProfile:
    scenario_path: Path
    title: str
    summary: str
    difficulty: Difficulty
    tags: tuple[str, ...]


def _registered_profiles() -> dict[str, _RegisteredProfile]:
    registered: dict[str, _RegisteredProfile] = {
        _BASE_PROFILE_ID: _RegisteredProfile(
            scenario_path=_BASE_SCENARIO_PATH,
            title="Synthetic rising seepage",
            summary="A bounded synthetic episode with increasing dam seepage risk.",
            difficulty=Difficulty.MEDIUM,
            tags=("dam", "monitoring", "seepage", "synthetic"),
        ),
    }
    for variant in dam_seepage_profile_variants():
        if variant.profile_id in registered:
            raise ValueError(f"dam-variant-collision: profile_id already registered: {variant.profile_id}")
        registered[variant.profile_id] = _RegisteredProfile(
            scenario_path=variant.scenario_path,
            title=variant.title,
            summary=variant.summary,
            difficulty=variant.difficulty,
            tags=variant.tags,
        )
    for profile_id in ("investigation-routine", "investigation-fault", "investigation-urgent-fault"):
        registered[profile_id] = _RegisteredProfile(
            scenario_path=Path(__file__).with_name(profile_id + ".json"),
            title="Costed seepage investigation",
            summary="A synthetic investigation with declared credits and a response deadline.",
            difficulty=Difficulty.MEDIUM,
            tags=("dam", "monitoring", "seepage", "synthetic", "investigation"),
        )
    return registered


@cache
def _scenario_bytes(profile_id: str) -> bytes:
    registered = _registered_profiles()
    if profile_id not in registered:
        raise ValueError(f"dam-profile-unknown: {profile_id}")
    return registered[profile_id].scenario_path.read_bytes()


@cache
def _scenario(profile_id: str) -> SeepageScenario:
    return SeepageScenario.model_validate_json(_scenario_bytes(profile_id))


@cache
def _profile_ref(profile_id: str) -> InteractiveWorldProfileRef:
    scenario = _scenario(profile_id)
    return InteractiveWorldProfileRef(
        task_world_id=scenario.task_world_id,
        profile_id=scenario.profile_id,
        profile_content_sha256=hashlib.sha256(_scenario_bytes(profile_id)).hexdigest(),
    )


def _load_profile(reference: InteractiveWorldProfileRef) -> LoadedInteractiveWorldProfile:
    current = _profile_ref(reference.profile_id)
    if reference != current:
        raise ValueError("dam seepage profile content differs")
    scenario = _scenario(reference.profile_id)
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
    """Return the current dam seepage build and its registered synthetic monitoring profiles."""
    registered = _registered_profiles()
    profile_ids = tuple(sorted(registered))
    profiles = tuple(_profile_ref(profile_id) for profile_id in profile_ids)
    return InteractiveWorldDefinition(
        identity=_WORLD_IDENTITY,
        build=_world_build(),
        title="Dam seepage monitoring",
        summary="Monitor rising seepage conditions and take safe, timely actions.",
        domain="civil",
        tags=("dam", "monitoring", "seepage"),
        capabilities=frozenset(),
        profiles=profiles,
        profile_identities=tuple(_PROFILE_IDENTITIES[profile_id] for profile_id in profile_ids),
        profile_metadata=tuple(
            InteractiveWorldProfileMetadata(
                profile_id=profile_id,
                title=registered[profile_id].title,
                summary=registered[profile_id].summary,
                category="monitoring",
                difficulty=registered[profile_id].difficulty,
                lifecycle=Lifecycle.ACTIVE,
                visibility=Visibility.PUBLIC,
                tags=registered[profile_id].tags,
            )
            for profile_id in profile_ids
        ),
        profile_loader=_load_profile,
    )
