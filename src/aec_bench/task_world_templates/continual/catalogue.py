# ABOUTME: Resolves continual-world definitions by stable identity and exact content reference.
# ABOUTME: Keeps concrete task imports in the external catalogue composition root.

from __future__ import annotations

from dataclasses import dataclass

from aec_bench.contracts.continual_world import ContinualWorldDefinitionRef
from aec_bench.task_world_templates.continual.definition import (
    ContinualWorldDefinition,
    ContinualWorldHarborPort,
)


@dataclass(frozen=True)
class ContinualWorldCatalogue:
    """Stable registry of task-owned continual-world definitions."""

    definitions: tuple[ContinualWorldDefinition, ...]

    def __post_init__(self) -> None:
        task_world_ids = tuple(definition.spec.task_world_id for definition in self.definitions)
        if len(task_world_ids) != len(set(task_world_ids)):
            raise ValueError("continual-world catalogue task world ids must be unique")
        harbor_execution_kinds = tuple(
            execution_kind
            for definition in self.definitions
            if definition.harbor_port is not None
            for execution_kind in definition.harbor_port.execution_kinds
        )
        if any(not execution_kind.strip() for execution_kind in harbor_execution_kinds):
            raise ValueError("Harbor execution kinds must not be empty")
        if len(harbor_execution_kinds) != len(set(harbor_execution_kinds)):
            raise ValueError("Harbor execution kinds must be unique")
        object.__setattr__(
            self,
            "definitions",
            tuple(sorted(self.definitions, key=lambda definition: definition.spec.task_world_id)),
        )

    def list_definition_refs(self) -> tuple[ContinualWorldDefinitionRef, ...]:
        """Return registered references in stable task-world order."""
        return tuple(definition.ref for definition in self.definitions)

    def get(self, task_world_id: str) -> ContinualWorldDefinition:
        """Resolve the current definition for new work by exact task-world ID."""
        for definition in self.definitions:
            if definition.spec.task_world_id == task_world_id:
                return definition
        known = ", ".join(definition.spec.task_world_id for definition in self.definitions)
        raise KeyError(f"unknown continual task world: {task_world_id}. Known: {known}")

    def resolve(self, reference: ContinualWorldDefinitionRef) -> ContinualWorldDefinition:
        """Resolve recovery work only when version and content identity still match."""
        definition = self.get(reference.task_world_id)
        if definition.ref != reference:
            raise ValueError(f"content-pinned definition does not match: {reference.task_world_id}")
        return definition

    def resolve_harbor(
        self,
        execution_kind: str,
    ) -> tuple[ContinualWorldDefinition, ContinualWorldHarborPort]:
        """Resolve one unique task-owned Harbor port by stable execution kind."""

        for definition in self.definitions:
            port = definition.harbor_port
            if port is not None and execution_kind in port.execution_kinds:
                return definition, port
        raise KeyError(f"unknown continual-world Harbor execution kind: {execution_kind}")
