# ABOUTME: Binds one continual-world definition to its task-owned profile loader.
# ABOUTME: Validates exact profile identity while leaving loaded profile values opaque.

from __future__ import annotations

import hashlib
import inspect
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from aec_bench.contracts.continual_world import (
    ContinualWorldDefinitionRef,
    ContinualWorldDefinitionSpec,
    ContinualWorldProfileRef,
)


@dataclass(frozen=True)
class LoadedContinualWorldProfile:
    """One exact profile reference and its task-owned validated value."""

    reference: ContinualWorldProfileRef
    value: object


@dataclass(frozen=True)
class ContinualWorldDefinition:
    """Registered world identity with a task-owned profile validation port."""

    spec: ContinualWorldDefinitionSpec
    profile_loader: Callable[[ContinualWorldProfileRef], LoadedContinualWorldProfile]

    @property
    def ref(self) -> ContinualWorldDefinitionRef:
        """Return the content-pinned world-definition reference."""
        return self.spec.ref

    def profile_ref(self, profile_id: str, profile_version: str) -> ContinualWorldProfileRef:
        """Resolve one supported profile by its exact public identity."""
        matching_id = tuple(profile for profile in self.spec.profiles if profile.profile_id == profile_id)
        if not matching_id:
            raise KeyError(f"unknown continual-world profile: {profile_id}")
        for profile in matching_id:
            if profile.profile_version == profile_version:
                return profile
        raise KeyError(f"unsupported continual-world profile version: {profile_id}@{profile_version}")

    def load_profile(self, reference: ContinualWorldProfileRef) -> LoadedContinualWorldProfile:
        """Validate and load only a profile declared by this exact definition."""
        if reference.task_world_id != self.spec.task_world_id:
            raise ValueError("continual-world profile belongs to another task world")
        current = self.profile_ref(reference.profile_id, reference.profile_version)
        if reference != current:
            raise ValueError(f"content-pinned profile does not match: {reference.profile_id}")
        loaded = self.profile_loader(reference)
        if loaded.reference != reference:
            raise ValueError("task-owned profile loader returned a different profile reference")
        return loaded


def python_source_sha256(source_owner: type[Any] | Callable[..., Any]) -> str:
    """Return the exact source digest for one registered Python port or value type."""
    try:
        source = inspect.getsource(source_owner).encode("utf-8")
    except (OSError, TypeError) as exc:
        raise ValueError("continual-world Python source identity is unavailable") from exc
    return hashlib.sha256(source).hexdigest()
