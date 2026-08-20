# ABOUTME: Defines provider-neutral Interactive World tasks and file-backed task loading.
# ABOUTME: Binds public task objectives to exact registered world and profile identities.

from __future__ import annotations

import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from aec_bench.contracts.commitments import canonical_json_sha256
from aec_bench.contracts.interactive_world import InteractiveWorldProfileRef, WorldBuildRef
from aec_bench.contracts.task_definition import Difficulty, Lifecycle, Visibility


@dataclass(frozen=True, slots=True)
class WorldTask:
    """One runnable objective bound to an exact registered world profile."""

    task_id: str
    task_revision: str
    instruction: str
    world: WorldBuildRef
    profile: InteractiveWorldProfileRef
    domain: str
    category: str
    difficulty: Difficulty
    lifecycle: Lifecycle
    visibility: Visibility
    tags: tuple[str, ...]

    def __post_init__(self) -> None:
        values = (self.task_id, self.task_revision, self.instruction, self.domain, self.category)
        if any(not value.strip() for value in values):
            raise ValueError("WorldTask text values must be non-empty")
        if self.profile.task_world_id != self.world.task_world_id:
            raise ValueError("WorldTask profile must belong to its world")
        if len(self.tags) != len(set(self.tags)) or any(not tag.strip() for tag in self.tags):
            raise ValueError("WorldTask tags must be distinct and non-empty")


def build_world_task(
    *,
    task_id: str,
    instruction: str,
    world: WorldBuildRef,
    profile: InteractiveWorldProfileRef,
    domain: str,
    category: str,
    difficulty: Difficulty,
    lifecycle: Lifecycle,
    visibility: Visibility,
    tags: tuple[str, ...],
) -> WorldTask:
    """Validate one task and derive its exact semantic revision."""

    task_id = task_id.strip()
    instruction = instruction.strip()
    payload = {
        "task_id": task_id,
        "instruction": instruction,
        "world": asdict(world),
        "profile": asdict(profile),
        "domain": domain,
        "category": category,
        "difficulty": difficulty.value,
        "lifecycle": lifecycle.value,
        "visibility": visibility.value,
        "tags": tags,
    }
    return WorldTask(
        task_id=task_id,
        task_revision=canonical_json_sha256(payload),
        instruction=instruction,
        world=world,
        profile=profile,
        domain=domain,
        category=category,
        difficulty=difficulty,
        lifecycle=lifecycle,
        visibility=visibility,
        tags=tags,
    )


def load_world_task(instance_dir: Path, tasks_root: Path) -> WorldTask:
    """Load and validate one portable ``world.toml`` task package."""

    from aec_bench.worlds.catalogue import _catalogue

    world_toml = instance_dir / "world.toml"
    instruction_file = instance_dir / "instruction.md"
    try:
        document = tomllib.loads(world_toml.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ValueError(f"missing world.toml: {world_toml}") from None
    try:
        instruction = instruction_file.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ValueError(f"missing instruction.md: {instruction_file}") from None

    world_data = _table(document, "world")
    profile_data = _table(document, "profile")
    metadata = _table(document, "metadata")
    world = WorldBuildRef(**world_data)
    profile = InteractiveWorldProfileRef(**profile_data)
    definition = _catalogue().resolve(world)
    if definition.profile_ref(profile.profile_id) != profile:
        raise ValueError(f"content-pinned profile does not match: {profile.profile_id}")
    registered = definition.metadata_for(profile.profile_id)
    supplied = (
        str(metadata.get("domain", "")),
        str(metadata.get("category", "")),
        Difficulty(str(metadata.get("difficulty", ""))),
        Lifecycle(str(metadata.get("lifecycle", ""))),
        Visibility(str(metadata.get("visibility", ""))),
        tuple(str(tag) for tag in metadata.get("tags", ())),
    )
    expected = (
        definition.domain,
        registered.category,
        registered.difficulty,
        registered.lifecycle,
        registered.visibility,
        registered.tags,
    )
    if supplied != expected:
        raise ValueError("world task metadata does not match the registered profile")
    return build_world_task(
        task_id=instance_dir.relative_to(tasks_root).as_posix(),
        instruction=instruction,
        world=world,
        profile=profile,
        domain=definition.domain,
        category=registered.category,
        difficulty=registered.difficulty,
        lifecycle=registered.lifecycle,
        visibility=registered.visibility,
        tags=registered.tags,
    )


def _table(document: dict[str, Any], name: str) -> dict[str, Any]:
    value = document.get(name)
    if not isinstance(value, dict):
        raise ValueError(f"world.toml requires [{name}]")
    return value


__all__ = ("WorldTask", "load_world_task")
