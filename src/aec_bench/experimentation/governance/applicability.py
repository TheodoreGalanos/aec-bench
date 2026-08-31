# ABOUTME: Implements the fixed-K reward-blind task profiler used for exact-bucket motif selection.
# ABOUTME: Binds safe declared structure to exact snapshots while abstaining from semantic decomposition claims.

from __future__ import annotations

from pathlib import Path
from typing import Literal, Self

from pydantic import field_validator, model_validator

from aec_bench.contracts.content_address import ContentAddressedModel
from aec_bench.contracts.harness_kernel import (
    FrozenStrictModel,
    KernelCapabilityRef,
    KernelRef,
    canonical_json_sha256,
    validate_sha256,
)
from aec_bench.contracts.task_review_snapshot import TaskReviewSnapshot
from aec_bench.contracts.task_snapshot import TaskSnapshotRef
from aec_bench.contracts.validators import NonEmptyStr
from aec_bench.experimentation.governance.motifs import MotifApplicabilityDescriptor
from aec_bench.harness.compilation.task_snapshot import resolve_task_material
from aec_bench.harness.compilation.task_surface import (
    DeclaredTaskSurface,
    TopologyBasis,
    project_declared_task_surface,
)
from aec_bench.harness.kernel_catalogue import (
    ApplicabilityProfilerRuntime,
    KernelRuntimeRegistry,
)
from aec_bench.tasks.registry import TaskRegistry

PROFILER_CAPABILITY_ID = "aecbench.profiler.declared-task-surface"


class TaskApplicabilityProjection(FrozenStrictModel):
    """One exact task snapshot paired with its safe declared profiler input."""

    snapshot: TaskSnapshotRef
    review: TaskReviewSnapshot | None = None
    surface: DeclaredTaskSurface

    @model_validator(mode="after")
    def validate_lineage(self) -> Self:
        if self.review is not None and self.review.task_id != self.snapshot.task_id:
            raise ValueError("applicability projection review does not match its task snapshot")
        return self

    @property
    def review_id(self) -> str:
        """Return one stable review identity without adding a second stored identity."""

        return self.review.profile_id if self.review is not None else f"unreviewed:{self.snapshot.task_id}"


class MotifApplicabilityAttestation(ContentAddressedModel):
    """Kernel-derived reward-blind applicability statement frozen before execution."""

    schema_version: Literal["aecbench.motif-applicability-attestation.v3"] = (
        "aecbench.motif-applicability-attestation.v3"
    )
    descriptor_source: Literal["kernel_reward_blind_task_profiler"] = "kernel_reward_blind_task_profiler"
    kernel_ref: KernelRef
    profiler_ref: KernelCapabilityRef
    source_snapshot_sha256: str
    profile_input_sha256: str
    review_lineage_ids: tuple[NonEmptyStr, ...]
    topology_bases: tuple[TopologyBasis, ...]
    projections: tuple[TaskApplicabilityProjection, ...]
    descriptor: MotifApplicabilityDescriptor

    @field_validator("source_snapshot_sha256", "profile_input_sha256")
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("review_lineage_ids")
    @classmethod
    def canonicalize_lineages(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        ordered = tuple(sorted(set(value)))
        if not ordered:
            raise ValueError("applicability attestation requires at least one review lineage")
        return ordered

    @field_validator("topology_bases")
    @classmethod
    def canonicalize_bases(cls, value: tuple[TopologyBasis, ...]) -> tuple[TopologyBasis, ...]:
        return tuple(sorted(set(value)))

    @field_validator("projections")
    @classmethod
    def canonicalize_projections(
        cls,
        value: tuple[TaskApplicabilityProjection, ...],
    ) -> tuple[TaskApplicabilityProjection, ...]:
        ordered = tuple(sorted(value, key=lambda projection: projection.snapshot.task_id))
        task_ids = tuple(projection.snapshot.task_id for projection in ordered)
        if not task_ids or len(task_ids) != len(set(task_ids)):
            raise ValueError("applicability attestation requires unique task projections")
        return ordered

    @model_validator(mode="after")
    def validate_attestation(self) -> Self:
        if self.profiler_ref.capability_id != PROFILER_CAPABILITY_ID:
            raise ValueError("applicability attestation does not use the fixed-K profiler")
        expected_snapshot = canonical_json_sha256(
            [projection.snapshot.model_dump(mode="json") for projection in self.projections]
        )
        if self.source_snapshot_sha256 != expected_snapshot:
            raise ValueError("applicability snapshot hash does not bind its task projections")
        expected_profile = canonical_json_sha256(_profile_input_payload(self.projections))
        if self.profile_input_sha256 != expected_profile:
            raise ValueError("applicability profile hash does not bind its reward-blind inputs")
        expected_lineages = tuple(sorted({projection.review_id for projection in self.projections}))
        if self.review_lineage_ids != expected_lineages:
            raise ValueError("applicability review lineages do not match its task projections")
        expected_bases = tuple(sorted({projection.surface.topology_basis for projection in self.projections}))
        if self.topology_bases != expected_bases:
            raise ValueError("applicability topology bases do not match its task projections")
        if self.descriptor != _aggregate_descriptor(self.projections):
            raise ValueError("applicability descriptor does not match its reward-blind task projections")
        return self


def profile_task_applicability(
    *,
    task_refs: tuple[str, ...],
    tasks_root: Path,
    registry: KernelRuntimeRegistry,
) -> MotifApplicabilityAttestation:
    """Run the allowlisted deterministic profiler over exact pre-execution task bytes."""

    profiler = registry.capability(PROFILER_CAPABILITY_ID)
    runtime = registry.resolve(profiler.ref).runtime
    if not isinstance(runtime, ApplicabilityProfilerRuntime):
        raise ValueError("fixed-K applicability capability does not resolve to its trusted runtime")
    material = resolve_task_material(task_refs=task_refs, tasks_root=tasks_root)
    reviews = {} if material.review is None else {review.task_id: review for review in material.review.tasks}
    task_registry = TaskRegistry(tasks_root=Path(tasks_root).resolve())
    task_registry.reload()
    tasks_by_id = {task.task_id: task for task in task_registry.all()}
    projections = tuple(
        TaskApplicabilityProjection(
            snapshot=snapshot,
            review=reviews.get(snapshot.task_id),
            surface=project_declared_task_surface(
                task=tasks_by_id[snapshot.task_id],
                task_dir=Path(tasks_root).resolve() / snapshot.task_id,
            ),
        )
        for snapshot in material.references
    )
    ordered = tuple(sorted(projections, key=lambda projection: projection.snapshot.task_id))
    return MotifApplicabilityAttestation(
        kernel_ref=registry.manifest.ref,
        profiler_ref=profiler.ref,
        source_snapshot_sha256=canonical_json_sha256(
            [projection.snapshot.model_dump(mode="json") for projection in ordered]
        ),
        profile_input_sha256=canonical_json_sha256(_profile_input_payload(ordered)),
        review_lineage_ids=tuple(projection.review_id for projection in ordered),
        topology_bases=tuple(projection.surface.topology_basis for projection in ordered),
        projections=ordered,
        descriptor=_aggregate_descriptor(ordered),
    )


def _profile_input_payload(
    projections: tuple[TaskApplicabilityProjection, ...],
) -> list[dict[str, object]]:
    return [
        {
            "task_id": projection.snapshot.task_id,
            "surface": projection.surface.model_dump(mode="json"),
        }
        for projection in projections
    ]


def _aggregate_descriptor(
    projections: tuple[TaskApplicabilityProjection, ...],
) -> MotifApplicabilityDescriptor:
    descriptors = tuple(_projection_descriptor(projection) for projection in projections)
    if not descriptors:
        raise ValueError("applicability profiler requires at least one task projection")
    if len(set(descriptors)) != 1:
        raise ValueError("task set contains heterogeneous applicability descriptors")
    return descriptors[0]


def _projection_descriptor(projection: TaskApplicabilityProjection) -> MotifApplicabilityDescriptor:
    surface = projection.surface
    return MotifApplicabilityDescriptor(
        task_pattern=surface.task_family_key,
        stage_pattern=_stage_pattern(surface),
        stage_count=len(surface.canonical_nodes),
        fanout_characteristic=(
            "bounded"
            if _maximum_degree(surface.canonical_nodes, surface.canonical_edges, outgoing=True) > 1
            else "none"
        ),
        branching_characteristic="conditional" if surface.branch_count else "none",
        evidence_surfaces=surface.evidence_surface_kinds,
        required_tool_surface=surface.declared_tool_ids,
        state_mode=surface.state_mode,
    )


def _stage_pattern(surface: DeclaredTaskSurface) -> str:
    if surface.topology_basis == "opaque_atomic":
        return "opaque_atomic"
    nodes = surface.canonical_nodes
    edges = surface.canonical_edges
    if len(nodes) == 1:
        return "single"
    maximum_out = _maximum_degree(nodes, edges, outgoing=True)
    maximum_in = _maximum_degree(nodes, edges, outgoing=False)
    if maximum_out > 1 and maximum_in > 1:
        return "fork_join"
    if maximum_out > 1:
        return "fan_out"
    if maximum_in > 1:
        return "fan_in"
    if len(edges) == len(nodes) - 1 and _connected(nodes, edges):
        return "serial"
    return "dag"


def _maximum_degree(
    nodes: tuple[str, ...],
    edges: tuple[tuple[str, str], ...],
    *,
    outgoing: bool,
) -> int:
    counts = {node: 0 for node in nodes}
    for source, target in edges:
        counts[source if outgoing else target] += 1
    return max(counts.values(), default=0)


def _connected(nodes: tuple[str, ...], edges: tuple[tuple[str, str], ...]) -> bool:
    neighbours: dict[str, set[str]] = {node: set() for node in nodes}
    for source, target in edges:
        neighbours[source].add(target)
        neighbours[target].add(source)
    seen: set[str] = set()
    pending = [nodes[0]]
    while pending:
        node = pending.pop()
        if node in seen:
            continue
        seen.add(node)
        pending.extend(neighbours[node] - seen)
    return len(seen) == len(nodes)
