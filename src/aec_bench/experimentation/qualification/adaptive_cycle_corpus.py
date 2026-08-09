# ABOUTME: Freezes independent discovery, calibration, and holdout task-review corpora.
# ABOUTME: Enforces explicit visibility, generation identity, and exact same-topology evidence splits.

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from aec_bench.contracts.harness_kernel import (
    ContentAddressedModel,
    FrozenStrictModel,
    validate_sha256,
)
from aec_bench.contracts.task_definition import Visibility
from aec_bench.contracts.task_generation import TaskGenerationIdentity
from aec_bench.contracts.validators import NonEmptyStr
from aec_bench.experimentation.governance.applicability import (
    MotifApplicabilityAttestation,
    profile_task_applicability,
)
from aec_bench.experimentation.governance.motifs import MotifApplicabilityDescriptor
from aec_bench.harness.kernel_catalogue import KernelRuntimeRegistry
from aec_bench.tasks.registry import TaskRegistry

CorpusSplitName = Literal["discovery", "calibration", "holdout"]


class AdaptiveCycleCorpusSplit(FrozenStrictModel):
    """One exact evidence split with task snapshots and declared generation provenance."""

    split: CorpusSplitName
    visibility: Visibility
    task_refs: tuple[NonEmptyStr, ...] = Field(min_length=2)
    generation_identities: tuple[TaskGenerationIdentity, ...] = Field(min_length=2)
    applicability: MotifApplicabilityAttestation

    @field_validator("task_refs")
    @classmethod
    def validate_task_refs(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if value != tuple(sorted(set(value))):
            raise ValueError("corpus split task refs must be canonical and unique")
        return value

    @field_validator("generation_identities")
    @classmethod
    def canonicalize_generation_identities(
        cls,
        value: tuple[TaskGenerationIdentity, ...],
    ) -> tuple[TaskGenerationIdentity, ...]:
        ordered = tuple(sorted(value, key=lambda identity: identity.task_id))
        task_ids = tuple(identity.task_id for identity in ordered)
        if len(task_ids) != len(set(task_ids)):
            raise ValueError("corpus split generation identities must use unique task ids")
        return ordered

    @model_validator(mode="after")
    def validate_split(self) -> Self:
        expected_visibility = Visibility.HOLDOUT if self.split == "holdout" else Visibility.PUBLIC
        if self.visibility is not expected_visibility:
            raise ValueError(f"{self.split} corpus visibility must be {expected_visibility.value}")
        identity_task_refs = tuple(identity.task_id for identity in self.generation_identities)
        if identity_task_refs != self.task_refs:
            raise ValueError("corpus split generation identities must cover its exact task refs")
        projected_task_refs = tuple(projection.snapshot.task_id for projection in self.applicability.projections)
        if projected_task_refs != self.task_refs:
            raise ValueError("corpus split applicability must cover its exact task refs")
        for projection in self.applicability.projections:
            task_review = projection.snapshot.task_review
            if task_review is None:
                raise ValueError("adaptive corpus tasks must declare task-review sidecars")
            if task_review.visibility is not self.visibility:
                raise ValueError("corpus split task snapshots do not match declared visibility")
            if projection.surface.topology_basis != "stage_handoff_graph":
                raise ValueError("adaptive corpus tasks must declare a stage/handoff graph")
        return self


class AdaptiveCycleCorpusManifest(ContentAddressedModel):
    """Immutable 2/2/2-or-larger corpus boundary for one adaptive research cycle."""

    schema_version: Literal["aecbench.adaptive-cycle-corpus.v2"] = "aecbench.adaptive-cycle-corpus.v2"
    corpus_id: NonEmptyStr
    discovery: AdaptiveCycleCorpusSplit
    repair_task_refs: tuple[NonEmptyStr, ...] = Field(min_length=1)
    calibration: AdaptiveCycleCorpusSplit
    holdout: AdaptiveCycleCorpusSplit
    applicability_descriptor: MotifApplicabilityDescriptor
    declared_surface_sha256: str

    @field_validator("repair_task_refs")
    @classmethod
    def validate_repair_task_refs(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if value != tuple(sorted(set(value))):
            raise ValueError("repair task refs must be canonical and unique")
        return value

    @field_validator("declared_surface_sha256")
    @classmethod
    def validate_declared_surface(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_manifest(self) -> Self:
        if (
            self.discovery.split != "discovery"
            or self.calibration.split != "calibration"
            or self.holdout.split != "holdout"
        ):
            raise ValueError("adaptive corpus fields must use their named evidence splits")
        if not set(self.repair_task_refs).issubset(self.discovery.task_refs):
            raise ValueError("repair tasks must be a subset of discovery tasks")

        split_task_sets = (
            set(self.discovery.task_refs),
            set(self.calibration.task_refs),
            set(self.holdout.task_refs),
        )
        if any(
            left.intersection(right)
            for index, left in enumerate(split_task_sets)
            for right in split_task_sets[index + 1 :]
        ):
            raise ValueError("corpus task refs must be disjoint across evidence splits")

        splits = (self.discovery, self.calibration, self.holdout)
        lineage_sets = tuple(set(split.applicability.review_lineage_ids) for split in splits)
        if any(
            left.intersection(right) for index, left in enumerate(lineage_sets) for right in lineage_sets[index + 1 :]
        ):
            raise ValueError("corpus review lineages must be disjoint across evidence splits")

        descriptors = tuple(split.applicability.descriptor for split in splits)
        if any(descriptor != descriptors[0] for descriptor in descriptors[1:]):
            raise ValueError("corpus evidence splits must use one applicability descriptor")
        if self.applicability_descriptor != descriptors[0]:
            raise ValueError("corpus descriptor does not match its split attestations")

        projections = tuple(projection for split in splits for projection in split.applicability.projections)
        package_hashes = tuple(projection.snapshot.package_sha256 for projection in projections)
        if len(package_hashes) != len(set(package_hashes)):
            raise ValueError("corpus task package snapshots must be unique")
        declared_surfaces = {
            projection.snapshot.task_review.declared_surface_sha256
            for projection in projections
            if projection.snapshot.task_review is not None
        }
        if declared_surfaces != {self.declared_surface_sha256}:
            raise ValueError("adaptive corpus must use exactly one declared surface")

        identities = tuple(identity for split in splits for identity in split.generation_identities)
        generation_keys = {
            (
                identity.template,
                identity.template_source_sha256,
                identity.seed,
                identity.instance_index,
            )
            for identity in identities
        }
        if len(generation_keys) != len(identities):
            raise ValueError("corpus generation identities must be unique")
        return self


def prepare_adaptive_cycle_corpus(
    *,
    corpus_id: str,
    discovery_task_refs: tuple[str, ...],
    repair_task_refs: tuple[str, ...],
    calibration_task_refs: tuple[str, ...],
    holdout_task_refs: tuple[str, ...],
    tasks_root: Path,
    registry: KernelRuntimeRegistry,
) -> AdaptiveCycleCorpusManifest:
    """Freeze exact task bytes and reward-blind structure before any campaign execution."""

    root = Path(tasks_root).resolve()
    discovery_refs = _validate_requested_refs(discovery_task_refs, label="discovery", minimum=2)
    repair_refs = _validate_requested_refs(repair_task_refs, label="repair", minimum=1)
    calibration_refs = _validate_requested_refs(calibration_task_refs, label="calibration", minimum=2)
    holdout_refs = _validate_requested_refs(holdout_task_refs, label="holdout", minimum=2)

    task_registry = TaskRegistry(tasks_root=root)
    task_registry.reload()
    splits = (
        _prepare_split(
            split="discovery",
            visibility=Visibility.PUBLIC,
            task_refs=discovery_refs,
            tasks_root=root,
            registry=registry,
            task_registry=task_registry,
        ),
        _prepare_split(
            split="calibration",
            visibility=Visibility.PUBLIC,
            task_refs=calibration_refs,
            tasks_root=root,
            registry=registry,
            task_registry=task_registry,
        ),
        _prepare_split(
            split="holdout",
            visibility=Visibility.HOLDOUT,
            task_refs=holdout_refs,
            tasks_root=root,
            registry=registry,
            task_registry=task_registry,
        ),
    )
    declared_surface = _single_declared_surface(splits)
    return AdaptiveCycleCorpusManifest(
        corpus_id=corpus_id,
        discovery=splits[0],
        repair_task_refs=repair_refs,
        calibration=splits[1],
        holdout=splits[2],
        applicability_descriptor=splits[0].applicability.descriptor,
        declared_surface_sha256=declared_surface,
    )


def _prepare_split(
    *,
    split: CorpusSplitName,
    visibility: Visibility,
    task_refs: tuple[str, ...],
    tasks_root: Path,
    registry: KernelRuntimeRegistry,
    task_registry: TaskRegistry,
) -> AdaptiveCycleCorpusSplit:
    identities = tuple(
        _load_generation_identity(
            task_id=task_id,
            tasks_root=tasks_root,
            expected_visibility=visibility,
            task_registry=task_registry,
        )
        for task_id in task_refs
    )
    applicability = profile_task_applicability(
        task_refs=task_refs,
        tasks_root=tasks_root,
        registry=registry,
    )
    return AdaptiveCycleCorpusSplit(
        split=split,
        visibility=visibility,
        task_refs=task_refs,
        generation_identities=identities,
        applicability=applicability,
    )


def _load_generation_identity(
    *,
    task_id: str,
    tasks_root: Path,
    expected_visibility: Visibility,
    task_registry: TaskRegistry,
) -> TaskGenerationIdentity:
    task = task_registry.get(task_id)
    if task is None:
        raise ValueError(f"adaptive corpus references an unknown task: {task_id}")
    declared_visibility = task.metadata.get("visibility")
    if declared_visibility != expected_visibility.value:
        raise ValueError(f"corpus task {task_id} must explicitly declare visibility {expected_visibility.value}")
    task_toml = tasks_root / task_id / "task.toml"
    payload = tomllib.loads(task_toml.read_text(encoding="utf-8"))
    generation = payload.get("generation")
    if not isinstance(generation, dict):
        raise ValueError(f"corpus task {task_id} must declare generated-instance provenance")
    try:
        return TaskGenerationIdentity.model_validate(
            {
                "task_id": task_id,
                "origin": generation.get("origin"),
                "template": generation.get("template"),
                "template_source_sha256": generation.get("template_source_sha256"),
                "seed": generation.get("seed"),
                "instance_index": generation.get("instance_index"),
            }
        )
    except ValueError as error:
        raise ValueError(f"corpus task {task_id} has invalid generated-instance provenance") from error


def _validate_requested_refs(
    value: tuple[str, ...],
    *,
    label: str,
    minimum: int,
) -> tuple[str, ...]:
    if len(value) < minimum:
        raise ValueError(f"{label} corpus requires at least {minimum} task refs")
    if value != tuple(sorted(set(value))):
        raise ValueError(f"{label} task refs must be canonical and unique")
    return value


def _single_declared_surface(
    splits: tuple[
        AdaptiveCycleCorpusSplit,
        AdaptiveCycleCorpusSplit,
        AdaptiveCycleCorpusSplit,
    ],
) -> str:
    surfaces = {
        projection.snapshot.task_review.declared_surface_sha256
        for split in splits
        for projection in split.applicability.projections
        if projection.snapshot.task_review is not None
    }
    if len(surfaces) != 1:
        raise ValueError("adaptive corpus must use exactly one declared surface")
    return next(iter(surfaces))
