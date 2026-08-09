# ABOUTME: Defines the closed registry of trusted operation handlers available to compiled programs.
# ABOUTME: Resolves only exact operation identities and validates binding and concurrency metadata.


from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from pydantic import JsonValue

from aec_bench.contracts.harness_instance import ProgramOperationRef

from .budget import OperationExecutionContext
from .contracts import OperationResult


class OperationHandler(Protocol):
    """Callable contract for code explicitly trusted and injected by the host application."""

    def __call__(
        self,
        arguments: Mapping[str, JsonValue],
        context: OperationExecutionContext,
    ) -> OperationResult: ...


@dataclass(frozen=True)
class OperationRegistration:
    """Trusted implementation bound to one exact Hx operation identity and binding lineage."""

    reference: ProgramOperationRef
    binding_ids: tuple[str, ...]
    handler: OperationHandler
    max_parallelism: int = 1

    def __post_init__(self) -> None:
        if not self.binding_ids or any(not binding_id.strip() for binding_id in self.binding_ids):
            raise ValueError("operation registration requires non-blank binding ids")
        if len(self.binding_ids) != len(set(self.binding_ids)):
            raise ValueError("operation registration binding ids must be unique")
        if not callable(self.handler):
            raise TypeError("operation registration handler must be callable")
        if isinstance(self.max_parallelism, bool) or not 1 <= self.max_parallelism <= 256:
            raise ValueError("operation registration max_parallelism must be between 1 and 256")


class OperationRegistry:
    """Closed registry of trusted handlers; it performs no dynamic imports or code lookup."""

    def __init__(self, registrations: tuple[OperationRegistration, ...]) -> None:
        by_id = {registration.reference.operation_id: registration for registration in registrations}
        if len(by_id) != len(registrations):
            raise ValueError("operation registry ids must be unique")
        self._registrations = by_id

    def registration(self, operation_id: str) -> OperationRegistration | None:
        """Return the trusted registration for an operation id, if one was injected."""

        return self._registrations.get(operation_id)

    def resolve(self, reference: ProgramOperationRef) -> OperationRegistration | None:
        """Resolve only when the injected registration matches the compiled content identity."""

        registration = self.registration(reference.operation_id)
        if registration is None or registration.reference != reference:
            return None
        return registration
