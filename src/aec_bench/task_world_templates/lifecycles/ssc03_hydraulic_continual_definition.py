# ABOUTME: Registers the SSC-03 hydraulic interaction world and its real public profiles.
# ABOUTME: Reuses the existing lifecycle adapter, variant records, resolver, smoke path, and verifier.

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

from aec_bench.contracts.continual_world import (
    ContinualWorldDefinitionRef,
    ContinualWorldDefinitionSpec,
    ContinualWorldProfileRef,
)
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
    python_source_sha256,
)
from aec_bench.task_world_templates.contracts import CompositeTaskWorldTemplate
from aec_bench.task_world_templates.hydraulics.revisions import build_hydraulic_revision_source_state
from aec_bench.task_world_templates.hydraulics.worlds.ssc03_detention_network import build_source_state
from aec_bench.task_world_templates.lifecycles import registered_lifecycle_adapter
from aec_bench.task_world_templates.lifecycles.ssc03_hydraulic_interaction_variants import (
    TEMPLATE_ID,
    get_ssc03_hydraulic_interaction_variant,
)
from aec_bench.task_world_templates.lifecycles.ssc03_hydraulic_rollout_adapter import (
    Ssc03HydraulicContinualBranchPort,
    ssc03_hydraulic_continual_branch_port,
    ssc03_hydraulic_rollout_source_sha256,
)

SSC03_HYDRAULIC_CONTINUAL_WORLD_ID = "aec.task_world.composite.hydraulic-interaction-lifecycle-review"
SSC03_HYDRAULIC_CONTINUAL_DEFINITION_VERSION = "1"
SSC03_HYDRAULIC_PROFILE_VERSION = "1"


@dataclass(frozen=True)
class Ssc03HydraulicContinualProfile:
    """Immutable SSC-03 profile binding over the existing lifecycle adapter."""

    reference: ContinualWorldProfileRef
    definition_reference: ContinualWorldDefinitionRef

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
        if _ssc03_definition_spec().ref != self.definition_reference:
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
    identity = adapter.identity()
    if identity.operation_resolver_factory is None or identity.smoke_environment_factory is None:
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
            "schema_version": "aecbench.ssc03-hydraulic-continual-profile.v1",
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
        profile_version=SSC03_HYDRAULIC_PROFILE_VERSION,
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
            definition_reference=_ssc03_definition_spec().ref,
        ),
    )


def _implementation_content_sha256(adapter: LifecycleWorldAdapter) -> str:
    return canonical_content_sha256(
        {
            "adapter": adapter.identity().model_dump(mode="json"),
            "definition_spec_builder": python_source_sha256(_ssc03_definition_spec),
            "implementation_identity_builder": python_source_sha256(_implementation_content_sha256),
            "loaded_profile": python_source_sha256(Ssc03HydraulicContinualProfile),
            "profile_loader": python_source_sha256(_load_ssc03_hydraulic_profile),
            "profile_reference": python_source_sha256(_profile_ref),
            "rollout_branch_port": python_source_sha256(Ssc03HydraulicContinualBranchPort),
            "rollout_branch_source": ssc03_hydraulic_rollout_source_sha256(),
        }
    )


def _ssc03_definition_spec() -> ContinualWorldDefinitionSpec:
    template, adapter = _validated_context()
    assert template.evidence_lifecycle is not None
    task_world_id = template.evidence_lifecycle.world_id
    profiles = tuple(_profile_ref(profile_id) for profile_id in adapter.variant_ids())
    return ContinualWorldDefinitionSpec(
        task_world_id=task_world_id,
        definition_version=SSC03_HYDRAULIC_CONTINUAL_DEFINITION_VERSION,
        implementation_content_sha256=_implementation_content_sha256(adapter),
        profiles=profiles,
    )


@cache
def ssc03_hydraulic_continual_world_definition() -> ContinualWorldDefinition:
    """Return the exact SSC-03 world definition over the existing lifecycle adapter."""
    return ContinualWorldDefinition(
        spec=_ssc03_definition_spec(),
        profile_loader=_load_ssc03_hydraulic_profile,
        branch_port=ssc03_hydraulic_continual_branch_port(),
    )
