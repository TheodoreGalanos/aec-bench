# ABOUTME: Registers the SSC-03 hydraulic interaction world and its real public profiles.
# ABOUTME: Reuses the existing lifecycle adapter, variant records, resolver, smoke path, and verifier.

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

from aec_bench.contracts.continual_world import ContinualWorldProfileRef, WorldBuildRef
from aec_bench.contracts.harness_kernel import canonical_content_sha256
from aec_bench.meta_harness.evidence_lifecycle_episode import LifecycleEpisodeEnvironment
from aec_bench.meta_harness.lifecycle_operation_protocol import LifecycleOperationResolver
from aec_bench.task_world_templates.catalogue import get_template
from aec_bench.task_world_templates.compiled_world import (
    CompiledLifecycleWorld,
    LifecycleWorldAdapter,
    build_compiled_world_envelope,
    validate_lifecycle_world_adapter,
)
from aec_bench.task_world_templates.continual.definition import (
    ContinualWorldDefinition,
    LoadedContinualWorldProfile,
    source_tree_world_build,
)
from aec_bench.task_world_templates.contracts import CompositeTaskWorldTemplate
from aec_bench.task_world_templates.hydraulics.revisions import build_hydraulic_revision_source_state
from aec_bench.task_world_templates.hydraulics.worlds.ssc03_detention_network import build_source_state
from aec_bench.task_world_templates.lifecycles import registered_lifecycle_adapter
from aec_bench.task_world_templates.lifecycles.ssc03_hydraulic_interaction_variants import (
    TEMPLATE_ID,
    get_ssc03_hydraulic_interaction_variant,
)

SSC03_HYDRAULIC_CONTINUAL_WORLD_ID = "aec.task_world.composite.hydraulic-interaction-lifecycle-review"


@dataclass(frozen=True)
class Ssc03HydraulicContinualProfile:
    """Immutable SSC-03 profile binding over the existing lifecycle adapter."""

    reference: ContinualWorldProfileRef
    world_build: WorldBuildRef

    @property
    def profile_id(self) -> str:
        """Return the selected immutable hydraulic profile identity."""
        return self.reference.profile_id

    def compile(self, output_dir: Path) -> CompiledLifecycleWorld:
        """Compile this exact profile through its existing registered adapter."""
        template, adapter = self._validated_port()
        template = CompositeTaskWorldTemplate.model_validate(template.model_dump(mode="json"))
        package_dir = adapter.materialize(
            Path(output_dir),
            template=template,
            variant_id=self.profile_id,
        )
        self._validated_package_port(package_dir)
        envelope = build_compiled_world_envelope(
            template=template,
            adapter=adapter,
            package_dir=package_dir,
            requested_variant_id=self.profile_id,
        )
        return CompiledLifecycleWorld(package_dir=package_dir, envelope=envelope)

    def build_operation_resolver(self, package_dir: Path, run_dir: Path) -> LifecycleOperationResolver | None:
        """Build the existing task-owned operation resolver for this profile."""
        adapter, _ = self._validated_package_port(package_dir)
        return adapter.build_operation_resolver(Path(package_dir), Path(run_dir))

    def build_smoke_environment(self, package_dir: Path) -> LifecycleEpisodeEnvironment | None:
        """Build the existing deterministic smoke environment for this profile."""
        adapter, _ = self._validated_package_port(package_dir)
        return adapter.build_smoke_environment(Path(package_dir))

    def validate_package(self, package_dir: Path) -> dict[str, Any] | None:
        """Validate the materialized package through the existing task port."""
        _, metadata = self._validated_package_port(package_dir)
        return metadata

    def verify(self, package_dir: Path, run_dir: Path) -> dict[str, Any]:
        """Verify one completed lifecycle through the existing task verifier."""
        adapter, _ = self._validated_package_port(package_dir)
        return adapter.verify(Path(package_dir), Path(run_dir))

    def _validated_port(self) -> tuple[CompositeTaskWorldTemplate, LifecycleWorldAdapter]:
        if _ssc03_world_build() != self.world_build:
            raise ValueError("SSC-03 continual-world definition implementation differs")
        current = _profile_ref(self.profile_id)
        if current != self.reference:
            raise ValueError("SSC-03 continual-world profile content differs")
        return _validated_context()

    def _validated_package_port(
        self,
        package_dir: Path,
    ) -> tuple[LifecycleWorldAdapter, dict[str, Any]]:
        _, adapter = self._validated_port()
        metadata = adapter.validate_package(Path(package_dir))
        if metadata is None or metadata.get("variant_id") != self.profile_id:
            raise ValueError("SSC-03 package belongs to another continual-world profile")
        return adapter, metadata


def _validated_context() -> tuple[CompositeTaskWorldTemplate, LifecycleWorldAdapter]:
    template = get_template(TEMPLATE_ID)
    lifecycle = template.evidence_lifecycle
    if lifecycle is None or lifecycle.world_id != SSC03_HYDRAULIC_CONTINUAL_WORLD_ID:
        raise ValueError("SSC-03 continual-world identity differs")
    adapter = registered_lifecycle_adapter(TEMPLATE_ID)
    validate_lifecycle_world_adapter(template, adapter)
    if "operations" not in adapter.identity().capabilities:
        raise ValueError("SSC-03 continual-world adapter is missing an executable lifecycle port")
    return template, adapter


def _profile_ref(profile_id: str) -> ContinualWorldProfileRef:
    template, _ = _validated_context()
    lifecycle = template.evidence_lifecycle
    if lifecycle is None:
        raise ValueError("SSC-03 template is missing its evidence lifecycle")
    variant = get_ssc03_hydraulic_interaction_variant(profile_id)
    profile_content_sha256 = canonical_content_sha256(
        {
            "task_world_id": lifecycle.world_id,
            "template": template.model_dump(mode="json"),
            "variant": variant.model_dump(mode="json"),
            "baseline_source": build_source_state().model_dump(mode="json"),
            "revision_source": build_hydraulic_revision_source_state(variant.revision_id).model_dump(mode="json"),
        }
    )
    return ContinualWorldProfileRef(
        task_world_id=lifecycle.world_id,
        profile_id=profile_id,
        profile_content_sha256=profile_content_sha256,
    )


def _load_ssc03_hydraulic_profile(reference: ContinualWorldProfileRef) -> LoadedContinualWorldProfile:
    current = _profile_ref(reference.profile_id)
    if current != reference:
        raise ValueError("SSC-03 continual-world profile content differs")
    variant = get_ssc03_hydraulic_interaction_variant(reference.profile_id)
    _, adapter = _validated_context()
    if adapter.variant_metadata(reference.profile_id) != variant.model_dump(mode="json"):
        raise ValueError("SSC-03 registered variant metadata differs")
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
    """Return the exact SSC-03 world definition over the existing lifecycle adapter."""
    _, adapter = _validated_context()
    return ContinualWorldDefinition(
        build=_ssc03_world_build(),
        profiles=tuple(_profile_ref(profile_id) for profile_id in adapter.variant_ids()),
        profile_loader=_load_ssc03_hydraulic_profile,
    )
