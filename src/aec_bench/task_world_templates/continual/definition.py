# ABOUTME: Binds one continual-world definition to its task-owned profile loader.
# ABOUTME: Validates exact profile identity while leaving loaded profile values opaque.

from __future__ import annotations

import hashlib
import inspect
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Protocol

from aec_bench.contracts.continual_world import (
    ContinualWorldActorRequest,
    ContinualWorldDefinitionRef,
    ContinualWorldDefinitionSpec,
    ContinualWorldProfileRef,
)
from aec_bench.contracts.world_interface import (
    WorldControlCapabilityCatalogue,
)
from aec_bench.task_world_templates.continual.branch_port import ContinualWorldBranchPort


@dataclass(frozen=True)
class LoadedContinualWorldProfile:
    """One exact profile reference and its task-owned validated value."""

    reference: ContinualWorldProfileRef
    value: object


class ContinualWorldExecutionPort(Protocol):
    """Task-owned actor and host-control adapter selected by the catalogue."""

    def actor_call(
        self,
        *,
        profile: LoadedContinualWorldProfile,
        run_root: Path,
        package_root: Path | None,
        request: ContinualWorldActorRequest,
    ) -> object:
        """Resolve and execute one call through the task's current episode owner."""

    def control_capabilities(
        self,
        *,
        profile: LoadedContinualWorldProfile,
        run_root: Path,
        package_root: Path | None,
        authorised_principal_ids: tuple[str, ...],
        authority_id: str,
    ) -> WorldControlCapabilityCatalogue:
        """Return the task's closed host-control catalogue."""

    def execute_control(
        self,
        *,
        profile: LoadedContinualWorldProfile,
        run_root: Path,
        package_root: Path | None,
        authorised_principal_ids: tuple[str, ...],
        request_payload: Mapping[str, object],
    ) -> object:
        """Validate and execute one task-owned control request."""


class ContinualWorldEvaluationPort(Protocol):
    """Task-owned evaluator selected through one registered definition."""

    def evaluate_run(
        self,
        *,
        profile: LoadedContinualWorldProfile,
        run_root: Path,
        imported_artifact_sha256: tuple[str, ...],
        evaluation_scope: Literal["complete_journey", "bounded_continuation"],
    ) -> object:
        """Evaluate one complete journey or verified bounded continuation."""


@dataclass(frozen=True, slots=True)
class ContinualWorldHarborBridgeIdentity:
    """Task-neutral facts needed by the main Harbor agent."""

    execution_kind: str
    bridge_mode: str
    manifest_sha256: str
    output_path: str


@dataclass(frozen=True, slots=True)
class ContinualWorldHarborSessionResult:
    """Task-neutral result returned by one registered Harbor session port."""

    output_dir: Path
    output_file: Path
    input_tokens: int
    output_tokens: int
    resolved_model: str
    session_id: str
    status: str


class ContinualWorldHarborPort(Protocol):
    """Task-owned Harbor adapter selected by a unique execution kind."""

    @property
    def execution_kinds(self) -> tuple[str, ...]: ...

    @property
    def default_max_turns(self) -> int: ...

    def validate_configuration(
        self,
        *,
        configuration: Mapping[str, Any],
        model_name: str,
    ) -> None:
        """Validate task-owned bridge and controller settings."""

    def load_bridge(self, environment_dir: Path) -> object:
        """Load and independently validate one exported task bridge."""

    def bridge_identity(self, bridge: object) -> ContinualWorldHarborBridgeIdentity:
        """Project only the bridge facts needed by generic orchestration."""

    def uses_model_controller(self, *, bridge: object, model_name: str) -> bool:
        """Return whether provider preflight is required for this execution."""

    def run_session(
        self,
        *,
        bridge: object,
        staging_dir: Path,
        session_identity: str,
        model_name: str,
        max_turns: int,
        registry: object | None,
    ) -> ContinualWorldHarborSessionResult:
        """Run one task-owned session and return generic upload metadata."""


@dataclass(frozen=True)
class ContinualWorldDefinition:
    """Registered world identity with a task-owned profile validation port."""

    spec: ContinualWorldDefinitionSpec
    profile_loader: Callable[[ContinualWorldProfileRef], LoadedContinualWorldProfile]
    branch_port: ContinualWorldBranchPort | None = None
    execution_port: ContinualWorldExecutionPort | None = None
    harbor_port: ContinualWorldHarborPort | None = None
    evaluation_port: ContinualWorldEvaluationPort | None = None

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
