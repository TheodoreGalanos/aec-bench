# ABOUTME: Binds one registered world build to its task-owned current profile loader.
# ABOUTME: Identifies executable source artifacts without embedding execution, provider, or evaluation ports.

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path

from aec_bench.contracts.identity import EntityIdentity, MemberIdentity
from aec_bench.contracts.interactive_world import InteractiveWorldProfileRef, WorldBuildRef
from aec_bench.contracts.task_definition import Difficulty, Lifecycle, Visibility


@dataclass(frozen=True, slots=True)
class InteractiveWorldOwnerDescriptor:
    """Describe one explicit owner entry in the generated world catalogue."""

    task_world_id: str
    entry_point: str

    def __post_init__(self) -> None:
        if not self.task_world_id.strip():
            raise ValueError("Interactive World owner task-world ID must be non-empty")
        module_name, separator, attribute_name = self.entry_point.partition(":")
        if not separator or not module_name.strip() or not attribute_name.strip():
            raise ValueError("Interactive World owner entry point must use module:attribute form")

    def load(self) -> InteractiveWorldDefinition:
        """Load and validate the concrete definition owned by this descriptor."""

        module_name, _, attribute_name = self.entry_point.partition(":")
        factory = getattr(import_module(module_name), attribute_name, None)
        if not callable(factory):
            raise TypeError(f"Interactive World owner entry point is not callable: {self.entry_point}")
        definition = factory()
        if not isinstance(definition, InteractiveWorldDefinition):
            raise TypeError(f"Interactive World owner returned another definition type: {self.entry_point}")
        if definition.build.task_world_id != self.task_world_id:
            raise ValueError(f"Interactive World owner ID differs from definition: {self.task_world_id}")
        return definition


@dataclass(frozen=True, slots=True)
class InteractiveWorldProfileMetadata:
    """Discovery and task-selection metadata for one registered profile."""

    profile_id: str
    title: str
    summary: str
    category: str
    difficulty: Difficulty
    lifecycle: Lifecycle
    visibility: Visibility
    tags: tuple[str, ...]

    def __post_init__(self) -> None:
        values = (self.profile_id, self.title, self.summary, self.category)
        if any(not value.strip() for value in values):
            raise ValueError("Interactive World profile metadata values must be non-empty")
        if len(self.tags) != len(set(self.tags)) or any(not tag.strip() for tag in self.tags):
            raise ValueError("Interactive World profile tags must be distinct and non-empty")


@dataclass(frozen=True)
class LoadedInteractiveWorldProfile:
    """One exact profile reference and its task-owned validated value."""

    reference: InteractiveWorldProfileRef
    value: object


@dataclass(frozen=True)
class InteractiveWorldDefinition:
    """One registered executable build and its current supported profiles."""

    identity: EntityIdentity
    build: WorldBuildRef
    title: str
    summary: str
    domain: str
    tags: tuple[str, ...]
    capabilities: frozenset[str]
    profiles: tuple[InteractiveWorldProfileRef, ...]
    profile_identities: tuple[MemberIdentity, ...]
    profile_metadata: tuple[InteractiveWorldProfileMetadata, ...]
    profile_loader: Callable[[InteractiveWorldProfileRef], LoadedInteractiveWorldProfile]

    def __post_init__(self) -> None:
        if not self.profiles:
            raise ValueError("Interactive World definition requires at least one profile")
        if any(not value.strip() for value in (self.title, self.summary, self.domain)):
            raise ValueError("Interactive World discovery metadata values must be non-empty")
        if len(self.tags) != len(set(self.tags)) or any(not tag.strip() for tag in self.tags):
            raise ValueError("Interactive World tags must be distinct and non-empty")
        if any(not capability.strip() for capability in self.capabilities):
            raise ValueError("Interactive World capabilities must be non-empty")
        if any(profile.task_world_id != self.build.task_world_id for profile in self.profiles):
            raise ValueError("Interactive World profiles must belong to the same task world")
        profile_ids = tuple(profile.profile_id for profile in self.profiles)
        if len(profile_ids) != len(set(profile_ids)):
            raise ValueError("Interactive World profile identities must be distinct")
        if profile_ids != tuple(sorted(profile_ids)):
            raise ValueError("Interactive World profiles must use stable order")
        metadata_ids = tuple(item.profile_id for item in self.profile_metadata)
        if metadata_ids != profile_ids:
            raise ValueError("Interactive World profile metadata must match profiles in stable order")
        if tuple(identity.registration_id for identity in self.profile_identities) != profile_ids:
            raise ValueError("Interactive World profile identities must match profiles in stable order")
        if len(self.profile_identities) != len({identity.id for identity in self.profile_identities}):
            raise ValueError("Interactive World profile UUIDs must be unique")
        if len(self.profile_identities) != len({identity.key for identity in self.profile_identities}):
            raise ValueError("Interactive World profile keys must be unique")
        if any(identity.parent_id != self.identity.id for identity in self.profile_identities):
            raise ValueError("Interactive World profile identities must belong to the definition")

    @property
    def ref(self) -> WorldBuildRef:
        """Return the executable world build selected for new work and recovery."""

        return self.build

    def profile_ref(self, profile_id: str) -> InteractiveWorldProfileRef:
        """Resolve one supported profile by its exact current identity."""

        for profile in self.profiles:
            if profile.profile_id == profile_id:
                return profile
        raise KeyError(f"unknown Interactive World profile: {profile_id}")

    def profile_identity(self, profile_id: str) -> MemberIdentity:
        """Resolve one profile entity by its exact owner registration ID."""

        for identity in self.profile_identities:
            if identity.registration_id == profile_id:
                return identity
        raise KeyError(f"unknown Interactive World profile identity: {profile_id}")

    def metadata_for(self, profile_id: str) -> InteractiveWorldProfileMetadata:
        """Return discovery and selection metadata for one supported profile."""

        for metadata in self.profile_metadata:
            if metadata.profile_id == profile_id:
                return metadata
        raise KeyError(f"unknown Interactive World profile: {profile_id}")

    def load_profile(self, reference: InteractiveWorldProfileRef) -> LoadedInteractiveWorldProfile:
        """Validate and load only a profile declared by this exact build."""

        if reference.task_world_id != self.build.task_world_id:
            raise ValueError("Interactive World profile belongs to another task world")
        current = self.profile_ref(reference.profile_id)
        if reference != current:
            raise ValueError(f"content-pinned profile does not match: {reference.profile_id}")
        loaded = self.profile_loader(reference)
        if loaded.reference != reference:
            raise ValueError("task-owned profile loader returned a different profile reference")
        return loaded


def source_tree_world_build(
    *,
    task_world_id: str,
    entry_point: str,
    roots: tuple[Path, ...],
) -> WorldBuildRef:
    """Identify the exact registered Python source artifacts used by one world build."""

    package_root = Path(__file__).resolve().parents[2]
    manifest: dict[str, str] = {}
    for root in roots:
        selected = Path(root).resolve(strict=True)
        candidates = (selected,) if selected.is_file() else tuple(sorted(selected.rglob("*.py")))
        for candidate in candidates:
            if candidate.is_symlink() or not candidate.is_file():
                raise ValueError(f"world-build source artifact is unsafe: {candidate}")
            try:
                relative = candidate.relative_to(package_root).as_posix()
            except ValueError as error:
                raise ValueError(f"world-build source artifact is outside aec_bench: {candidate}") from error
            manifest[relative] = hashlib.sha256(candidate.read_bytes()).hexdigest()
    if not manifest:
        raise ValueError("world build requires at least one source artifact")
    payload = json.dumps(manifest, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return WorldBuildRef(
        task_world_id=task_world_id,
        entry_point=entry_point,
        artifact_sha256=hashlib.sha256(payload).hexdigest(),
    )
