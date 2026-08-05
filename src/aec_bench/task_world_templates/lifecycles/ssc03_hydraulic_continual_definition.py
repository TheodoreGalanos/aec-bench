# ABOUTME: Registers the SSC-03 hydraulic interaction world and its real public profiles.
# ABOUTME: Composes the task-owned lifecycle functions directly into the continual runtime.

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

from aec_bench.contracts.continual_world import ContinualWorldProfileRef, WorldBuildRef
from aec_bench.contracts.harness_kernel import canonical_content_sha256
from aec_bench.meta_harness.evidence_lifecycle_episode import LifecycleEpisodeEnvironment
from aec_bench.meta_harness.lifecycle_operation_protocol import LifecycleOperationResolver
from aec_bench.task_world_templates.compiled_world import CompiledLifecycleWorld, compile_lifecycle
from aec_bench.task_world_templates.continual.definition import (
    ContinualWorldDefinition,
    LoadedContinualWorldProfile,
    source_tree_world_build,
)
from aec_bench.task_world_templates.hydraulics.revisions import build_hydraulic_revision_source_state
from aec_bench.task_world_templates.hydraulics.worlds.ssc03_detention_network import build_source_state
from aec_bench.task_world_templates.lifecycles.ssc03_hydraulic_interaction import (
    LIFECYCLE,
    METADATA,
    build_ssc03_hydraulic_operation_resolver,
    validated_ssc03_hydraulic_interaction_variant,
    verify_ssc03_hydraulic_interaction_lifecycle,
)
from aec_bench.task_world_templates.lifecycles.ssc03_hydraulic_interaction_smoke import (
    build_ssc03_hydraulic_smoke_environment,
)
from aec_bench.task_world_templates.lifecycles.ssc03_hydraulic_interaction_variants import (
    TEMPLATE_ID,
    get_ssc03_hydraulic_interaction_variant,
    list_ssc03_hydraulic_interaction_variant_ids,
)

SSC03_HYDRAULIC_CONTINUAL_WORLD_ID = "aec.task_world.composite.hydraulic-interaction-lifecycle-review"


@dataclass(frozen=True)
class Ssc03HydraulicContinualProfile:
    """Immutable SSC-03 profile binding over the task-owned lifecycle functions."""

    reference: ContinualWorldProfileRef
    world_build: WorldBuildRef

    @property
    def profile_id(self) -> str:
        """Return the selected immutable hydraulic profile identity."""
        return self.reference.profile_id

    def compile(self, output_dir: Path) -> CompiledLifecycleWorld:
        """Compile this exact profile through its task-owned materializer."""
        self._validate_binding()
        compiled = compile_lifecycle(TEMPLATE_ID, Path(output_dir), variant_id=self.profile_id)
        self._validate_package(compiled.package_dir)
        return compiled

    def build_operation_resolver(self, package_dir: Path, run_dir: Path) -> LifecycleOperationResolver | None:
        """Build the task-owned operation resolver for this profile."""
        self._validate_package(package_dir)
        return build_ssc03_hydraulic_operation_resolver(Path(package_dir), Path(run_dir))

    def build_smoke_environment(self, package_dir: Path) -> LifecycleEpisodeEnvironment | None:
        """Build the deterministic smoke environment for this profile."""
        self._validate_package(package_dir)
        return build_ssc03_hydraulic_smoke_environment(Path(package_dir))

    def validate_package(self, package_dir: Path) -> dict[str, Any] | None:
        """Validate the materialized package through the task-owned validator."""
        return self._validate_package(package_dir)

    def verify(self, package_dir: Path, run_dir: Path) -> dict[str, Any]:
        """Verify one completed lifecycle through the task-owned verifier."""
        self._validate_package(package_dir)
        return verify_ssc03_hydraulic_interaction_lifecycle(Path(package_dir), Path(run_dir))

    def _validate_binding(self) -> None:
        if _ssc03_world_build() != self.world_build:
            raise ValueError("SSC-03 continual-world definition implementation differs")
        current = _profile_ref(self.profile_id)
        if current != self.reference:
            raise ValueError("SSC-03 continual-world profile content differs")
        _validate_context()

    def _validate_package(self, package_dir: Path) -> dict[str, Any]:
        self._validate_binding()
        metadata = validated_ssc03_hydraulic_interaction_variant(Path(package_dir))
        if metadata.get("variant_id") != self.profile_id:
            raise ValueError("SSC-03 package belongs to another continual-world profile")
        return metadata


def _validate_context() -> None:
    if METADATA.template_id != TEMPLATE_ID or LIFECYCLE.world_id != SSC03_HYDRAULIC_CONTINUAL_WORLD_ID:
        raise ValueError("SSC-03 continual-world identity differs")


def _profile_ref(profile_id: str) -> ContinualWorldProfileRef:
    _validate_context()
    variant = get_ssc03_hydraulic_interaction_variant(profile_id)
    profile_content_sha256 = canonical_content_sha256(
        {
            "task_world_id": LIFECYCLE.world_id,
            "metadata": METADATA.model_dump(mode="json"),
            "lifecycle": LIFECYCLE.model_dump(mode="json"),
            "variant": variant.model_dump(mode="json"),
            "baseline_source": build_source_state().model_dump(mode="json"),
            "revision_source": build_hydraulic_revision_source_state(variant.revision_id).model_dump(mode="json"),
        }
    )
    return ContinualWorldProfileRef(
        task_world_id=LIFECYCLE.world_id,
        profile_id=profile_id,
        profile_content_sha256=profile_content_sha256,
    )


def _load_ssc03_hydraulic_profile(reference: ContinualWorldProfileRef) -> LoadedContinualWorldProfile:
    current = _profile_ref(reference.profile_id)
    if current != reference:
        raise ValueError("SSC-03 continual-world profile content differs")
    _validate_context()
    return LoadedContinualWorldProfile(
        reference=reference,
        value=Ssc03HydraulicContinualProfile(
            reference=reference,
            world_build=_ssc03_world_build(),
        ),
    )


@cache
def _ssc03_world_build() -> WorldBuildRef:
    source_root = Path(__file__).resolve().parents[1]
    return source_tree_world_build(
        task_world_id=SSC03_HYDRAULIC_CONTINUAL_WORLD_ID,
        entry_point=(
            "aec_bench.task_world_templates.lifecycles.ssc03_hydraulic_continual_definition:"
            "ssc03_hydraulic_continual_world_definition"
        ),
        roots=(
            Path(__file__),
            source_root / "compiled_world.py",
            source_root / "lifecycles",
            source_root / "hydraulics",
            source_root / "continual",
        ),
    )


@cache
def ssc03_hydraulic_continual_world_definition() -> ContinualWorldDefinition:
    """Return the exact SSC-03 world definition over task-owned lifecycle functions."""
    _validate_context()
    return ContinualWorldDefinition(
        build=_ssc03_world_build(),
        profiles=tuple(_profile_ref(profile_id) for profile_id in list_ssc03_hydraulic_interaction_variant_ids()),
        profile_loader=_load_ssc03_hydraulic_profile,
    )
