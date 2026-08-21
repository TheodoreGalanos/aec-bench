# ABOUTME: Provides public discovery, task construction, and profile loading for Interactive Worlds.
# ABOUTME: Projects the explicit registered catalogue without exposing internal loaders.

from __future__ import annotations

from dataclasses import dataclass

from aec_bench.worlds.branching import branch_world, tasks_for_branches
from aec_bench.worlds.catalogue import _catalogue
from aec_bench.worlds.runtime.definition import LoadedInteractiveWorldProfile
from aec_bench.worlds.tasks import WorldTask, build_world_task, load_world_task


@dataclass(frozen=True, slots=True)
class WorldProfileInfo:
    id: str
    title: str
    summary: str
    tags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class WorldInfo:
    id: str
    title: str
    summary: str
    domain: str
    tags: tuple[str, ...]
    capabilities: frozenset[str]
    profiles: tuple[WorldProfileInfo, ...]


def list() -> tuple[WorldInfo, ...]:
    """Return registered worlds in stable world-ID order."""

    return tuple(_world_info(definition) for definition in _catalogue().definitions)


def find(query: str) -> tuple[WorldInfo, ...]:
    """Find registered worlds by deterministic case-insensitive text match."""

    needle = query.strip().casefold()
    if not needle:
        return ()
    return tuple(
        info
        for info in list()
        if needle in " ".join((info.id, info.title, info.summary, info.domain, *info.tags)).casefold()
    )


def get(world_id: str) -> WorldInfo:
    """Return public information for one exact registered world ID."""

    return _world_info(_catalogue().get(world_id))


def profiles(world_id: str) -> tuple[WorldProfileInfo, ...]:
    """Return one world's profiles in stable profile-ID order."""

    return get(world_id).profiles


def task(
    world_id: str,
    *,
    profile: str,
    instruction: str,
    task_id: str | None = None,
) -> WorldTask:
    """Create one provider-neutral task from registered world and profile IDs."""

    definition = _catalogue().get(world_id)
    profile_ref = definition.profile_ref(profile)
    metadata = definition.metadata_for(profile)
    return build_world_task(
        task_id=task_id or f"{world_id}/{profile}",
        instruction=instruction,
        world=definition.ref,
        profile=profile_ref,
        domain=definition.domain,
        category=metadata.category,
        difficulty=metadata.difficulty,
        lifecycle=metadata.lifecycle,
        visibility=metadata.visibility,
        tags=metadata.tags,
    )


def load_profile(task: WorldTask) -> LoadedInteractiveWorldProfile:
    """Load the exact registered task-owned profile selected by a WorldTask."""

    return _catalogue().resolve(task.world).load_profile(task.profile)


def _world_info(definition: object) -> WorldInfo:
    from aec_bench.worlds.runtime.definition import InteractiveWorldDefinition

    if not isinstance(definition, InteractiveWorldDefinition):
        raise TypeError("world catalogue returned another definition type")
    profile_info = tuple(
        WorldProfileInfo(id=item.profile_id, title=item.title, summary=item.summary, tags=item.tags)
        for item in definition.profile_metadata
    )
    return WorldInfo(
        id=definition.ref.task_world_id,
        title=definition.title,
        summary=definition.summary,
        domain=definition.domain,
        tags=definition.tags,
        capabilities=definition.capabilities,
        profiles=profile_info,
    )


__all__ = (
    "WorldInfo",
    "WorldProfileInfo",
    "WorldTask",
    "branch_world",
    "find",
    "get",
    "list",
    "load_profile",
    "load_world_task",
    "profiles",
    "task",
    "tasks_for_branches",
)
