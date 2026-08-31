# ABOUTME: Resolves Interactive World definitions by stable identity and exact content reference.
# ABOUTME: Loads the committed generated owner composition without concrete imports here.

from __future__ import annotations

from dataclasses import dataclass
from functools import cache

from aec_bench.contracts.interactive_world import WorldBuildRef
from aec_bench.worlds.generated_catalogue import load_world_definitions
from aec_bench.worlds.runtime.definition import InteractiveWorldDefinition


@dataclass(frozen=True)
class WorldCatalogue:
    """Stable registry of task-owned Interactive World definitions."""

    definitions: tuple[InteractiveWorldDefinition, ...]

    def __post_init__(self) -> None:
        task_world_ids = tuple(definition.build.task_world_id for definition in self.definitions)
        if len(task_world_ids) != len(set(task_world_ids)):
            raise ValueError("Interactive World catalogue task world ids must be unique")
        identities = [
            identity
            for definition in self.definitions
            for identity in (definition.identity, *definition.profile_identities)
        ]
        if len(identities) != len({identity.id for identity in identities}):
            raise ValueError("Interactive World catalogue entity UUIDs must be unique")
        if len(identities) != len({identity.key for identity in identities}):
            raise ValueError("Interactive World catalogue entity keys must be unique")
        object.__setattr__(
            self,
            "definitions",
            tuple(sorted(self.definitions, key=lambda definition: definition.build.task_world_id)),
        )

    def list_definition_refs(self) -> tuple[WorldBuildRef, ...]:
        """Return registered references in stable task-world order."""
        return tuple(definition.ref for definition in self.definitions)

    def get(self, task_world_id: str) -> InteractiveWorldDefinition:
        """Resolve the current definition for new work by exact task-world ID."""
        for definition in self.definitions:
            if definition.build.task_world_id == task_world_id:
                return definition
        known = ", ".join(definition.build.task_world_id for definition in self.definitions)
        raise KeyError(f"unknown Interactive World: {task_world_id}. Known: {known}")

    def resolve(self, reference: WorldBuildRef) -> InteractiveWorldDefinition:
        """Resolve recovery work only when executable artifact identity still matches."""
        definition = self.get(reference.task_world_id)
        if definition.build != reference:
            raise ValueError(f"world build does not match: {reference.task_world_id}")
        return definition


@cache
def _catalogue() -> WorldCatalogue:
    """Return the generated registered causal worlds."""
    return WorldCatalogue(definitions=load_world_definitions())
