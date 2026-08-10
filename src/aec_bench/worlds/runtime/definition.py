# ABOUTME: Binds one registered world build to its task-owned current profile loader.
# ABOUTME: Identifies executable source artifacts without embedding execution, provider, or evaluation ports.

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from aec_bench.contracts.interactive_world import InteractiveWorldProfileRef, WorldBuildRef


@dataclass(frozen=True)
class LoadedInteractiveWorldProfile:
    """One exact profile reference and its task-owned validated value."""

    reference: InteractiveWorldProfileRef
    value: object


@dataclass(frozen=True)
class InteractiveWorldDefinition:
    """One registered executable build and its current supported profiles."""

    build: WorldBuildRef
    profiles: tuple[InteractiveWorldProfileRef, ...]
    profile_loader: Callable[[InteractiveWorldProfileRef], LoadedInteractiveWorldProfile]

    def __post_init__(self) -> None:
        if not self.profiles:
            raise ValueError("Interactive World definition requires at least one profile")
        if any(profile.task_world_id != self.build.task_world_id for profile in self.profiles):
            raise ValueError("Interactive World profiles must belong to the same task world")
        profile_ids = tuple(profile.profile_id for profile in self.profiles)
        if len(profile_ids) != len(set(profile_ids)):
            raise ValueError("Interactive World profile identities must be distinct")
        if profile_ids != tuple(sorted(profile_ids)):
            raise ValueError("Interactive World profiles must use stable order")

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
