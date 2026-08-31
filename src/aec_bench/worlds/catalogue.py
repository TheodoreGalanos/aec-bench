# ABOUTME: Resolves Interactive World definitions by stable identity and exact content reference.
# ABOUTME: Loads the committed generated owner composition without concrete imports here.

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import cache
from types import MappingProxyType
from uuid import UUID

from aec_bench.contracts.interactive_world import WorldBuildRef
from aec_bench.worlds.generated_catalogue import load_world_definitions
from aec_bench.worlds.runtime.definition import InteractiveWorldDefinition


@dataclass(frozen=True)
class WorldCatalogue:
    """Stable registry of task-owned Interactive World definitions."""

    definitions: tuple[InteractiveWorldDefinition, ...]
    _by_task_world_id: Mapping[str, InteractiveWorldDefinition] = field(init=False, repr=False, compare=False)
    _by_key: Mapping[str, InteractiveWorldDefinition] = field(init=False, repr=False, compare=False)
    _by_id: Mapping[UUID, InteractiveWorldDefinition] = field(init=False, repr=False, compare=False)

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
        definitions = tuple(sorted(self.definitions, key=lambda definition: definition.build.task_world_id))
        object.__setattr__(self, "definitions", definitions)
        object.__setattr__(
            self,
            "_by_task_world_id",
            MappingProxyType({definition.build.task_world_id: definition for definition in definitions}),
        )
        object.__setattr__(
            self,
            "_by_key",
            MappingProxyType({str(definition.identity.key): definition for definition in definitions}),
        )
        object.__setattr__(
            self,
            "_by_id",
            MappingProxyType({definition.identity.id: definition for definition in definitions}),
        )

    def list_definition_refs(self) -> tuple[WorldBuildRef, ...]:
        """Return registered references in stable task-world order."""
        return tuple(definition.ref for definition in self.definitions)

    def get(self, task_world_id: str) -> InteractiveWorldDefinition:
        """Resolve the current definition for new work by exact task-world ID."""
        try:
            return self._by_task_world_id[task_world_id]
        except KeyError as error:
            known = ", ".join(self._by_task_world_id)
            raise KeyError(f"unknown Interactive World: {task_world_id}. Known: {known}") from error

    def get_versioned(self, identity: UUID | str, *, version: int) -> InteractiveWorldDefinition:
        """Resolve one current definition by UUID or canonical key and exact version."""

        if version <= 0:
            raise ValueError("Interactive World version must be positive")
        definition = self._by_id.get(identity) if isinstance(identity, UUID) else self._by_key.get(identity)
        if definition is None or definition.identity.version != version:
            raise KeyError(f"unknown Interactive World identity and version: {identity} version {version}")
        return definition

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
