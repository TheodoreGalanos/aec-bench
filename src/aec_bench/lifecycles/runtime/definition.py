# ABOUTME: Defines the task-neutral value types used by lifecycle owner descriptors.
# ABOUTME: Keeps lifecycle composition data separate from lookup and execution policy.

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aec_bench.contracts.evidence_lifecycle import EvidenceLifecycleSpec, LifecycleTaskMetadata
from aec_bench.contracts.identity import EntityIdentity, MemberIdentity
from aec_bench.lifecycles.runtime.episode import LifecycleEpisodeEnvironment
from aec_bench.lifecycles.runtime.operation_protocol import LifecycleOperationResolver


@dataclass(frozen=True, slots=True)
class LifecycleDefinition:
    """One concrete lifecycle build and its current owner-local behavior."""

    metadata: LifecycleTaskMetadata
    lifecycle: EvidenceLifecycleSpec
    materializer: Callable[..., Path]
    verifier: Callable[[Path, Path], dict[str, Any]]
    executable_source_roots: tuple[Path, ...]
    variant_identities: tuple[MemberIdentity, ...] = ()
    variant_validator: Callable[[Path], dict[str, Any]] | None = None
    variant_ids: Callable[[], tuple[str, ...]] | None = None
    variant_metadata: Callable[[str], Any] | None = None
    operation_resolver: Callable[[Path, Path], LifecycleOperationResolver] | None = None
    smoke_environment: Callable[[Path], LifecycleEpisodeEnvironment] | None = None

    @property
    def identity(self) -> EntityIdentity:
        """Return the stable identity registered for this lifecycle."""

        return self.metadata.identity

    def __post_init__(self) -> None:
        if self.variant_ids is None and self.variant_identities:
            raise ValueError("lifecycle without variants must not declare member identities")
        if self.variant_ids is not None:
            registered_variant_ids = tuple(self.variant_ids())
            if len(registered_variant_ids) != len(set(registered_variant_ids)):
                raise ValueError("lifecycle registered variant IDs must be unique")
            variant_ids = tuple(sorted(registered_variant_ids))
            member_ids = tuple(identity.registration_id for identity in self.variant_identities)
            if member_ids != variant_ids:
                raise ValueError("lifecycle variant identities must match registered variants in stable order")
        if len(self.variant_identities) != len({identity.id for identity in self.variant_identities}):
            raise ValueError("lifecycle variant UUIDs must be unique")
        if len(self.variant_identities) != len({identity.key for identity in self.variant_identities}):
            raise ValueError("lifecycle variant keys must be unique")
        if any(identity.parent_id != self.identity.id for identity in self.variant_identities):
            raise ValueError("lifecycle variant identities must belong to the lifecycle")


@dataclass(frozen=True, slots=True)
class LifecycleOwnerDescriptor:
    """One immutable owner-local lifecycle descriptor for generated composition."""

    definition: LifecycleDefinition

    def __post_init__(self) -> None:
        if not isinstance(self.definition, LifecycleDefinition):
            raise TypeError("lifecycle owner descriptor requires a LifecycleDefinition")

    def load(self) -> LifecycleDefinition:
        """Return the owner definition after descriptor validation."""

        return self.definition


def shared_executable_source_roots() -> tuple[Path, ...]:
    """Return source roots shared by every maintained lifecycle build."""

    package_root = Path(__file__).resolve().parents[2]
    return (
        Path(__file__).resolve(),
        package_root / "contracts" / "evidence_lifecycle.py",
        package_root / "contracts" / "lifecycle_evaluation.py",
        package_root / "contracts" / "trial_record.py",
        package_root / "contracts" / "validators.py",
        package_root / "evaluation" / "lifecycle.py",
        package_root / "ledger" / "durability.py",
        package_root / "ledger" / "immutable_byte_store.py",
        package_root / "ledger" / "local_lock.py",
        package_root / "ledger" / "process_log.py",
        package_root / "lifecycles" / "__init__.py",
        package_root / "lifecycles" / "runtime",
    )
