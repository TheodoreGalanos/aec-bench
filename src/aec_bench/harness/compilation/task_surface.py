# ABOUTME: Projects reward-blind topology, tool, and evidence declarations from runnable task packages.
# ABOUTME: Excludes instructions, expected answers, outcomes, examples, and trajectories from applicability input.

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal, Self

import yaml
from pydantic import Field, field_validator, model_validator

from aec_bench.contracts.harness_kernel import FrozenStrictModel
from aec_bench.contracts.task_definition import TaskDefinition
from aec_bench.contracts.validators import NonEmptyStr
from aec_bench.evaluation.task_review import TASK_REVIEW_SIDECARS

TopologyBasis = Literal["opaque_atomic", "evidence_lifecycle", "stage_handoff_graph"]


class DeclaredTaskSurface(FrozenStrictModel):
    """Safe pre-execution projection used by the fixed applicability profiler."""

    task_family_key: NonEmptyStr
    task_unit: NonEmptyStr
    declared_tool_ids: tuple[NonEmptyStr, ...]
    evidence_surface_kinds: tuple[NonEmptyStr, ...]
    topology_basis: TopologyBasis
    canonical_nodes: tuple[NonEmptyStr, ...]
    canonical_edges: tuple[tuple[NonEmptyStr, NonEmptyStr], ...]
    branch_count: int = Field(ge=0)
    state_mode: Literal["ephemeral"] = "ephemeral"

    @field_validator("declared_tool_ids", "evidence_surface_kinds", "canonical_nodes")
    @classmethod
    def canonicalize_values(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("declared task surface values must be unique")
        return tuple(sorted(value))

    @field_validator("canonical_edges")
    @classmethod
    def canonicalize_edges(
        cls,
        value: tuple[tuple[str, str], ...],
    ) -> tuple[tuple[str, str], ...]:
        if len(value) != len(set(value)):
            raise ValueError("declared topology edges must be unique")
        return tuple(sorted(value))

    @model_validator(mode="after")
    def validate_graph(self) -> Self:
        if not self.canonical_nodes:
            raise ValueError("declared task topology requires at least one node")
        known = set(self.canonical_nodes)
        for source, target in self.canonical_edges:
            if source not in known or target not in known:
                raise ValueError("declared topology edge references an unknown node")
            if source == target:
                raise ValueError("declared topology cannot contain self edges")
        _validate_acyclic(self.canonical_nodes, self.canonical_edges)
        return self


def project_declared_task_surface(*, task: TaskDefinition, task_dir: Path) -> DeclaredTaskSurface:
    """Project one task using a closed allowlist of declarations available before execution."""

    return project_declared_task_surface_payload(
        task=task,
        payload=_sidecar_payload(Path(task_dir)),
    )


def project_declared_task_surface_payload(
    *,
    task: TaskDefinition,
    payload: dict[str, Any],
) -> DeclaredTaskSurface:
    """Project the same safe surface from host-owned sidecar bytes outside a public task."""
    topology_basis, nodes, edges = _declared_topology(payload)
    task_unit = _non_empty(payload.get("task_unit")) or task.task_type
    pattern = _non_empty(payload.get("pattern"))
    task_family_key = (
        f"declared:{pattern}"
        if pattern is not None
        else f"registry:{task.domain}/{task.category}/{task.task_type}/{task_unit}"
    )
    return DeclaredTaskSurface(
        task_family_key=task_family_key,
        task_unit=task_unit,
        declared_tool_ids=tuple(tool.name for tool in task.environment.tools),
        evidence_surface_kinds=_evidence_surfaces(payload),
        topology_basis=topology_basis,
        canonical_nodes=nodes,
        canonical_edges=edges,
        branch_count=_branch_count(payload),
    )


def _sidecar_payload(task_dir: Path) -> dict[str, Any]:
    sidecars = tuple(task_dir / name for name in TASK_REVIEW_SIDECARS if (task_dir / name).is_file())
    if len(sidecars) > 1:
        raise ValueError("task package declares multiple task-review sidecars")
    if not sidecars:
        return {}
    sidecar = sidecars[0]
    if sidecar.suffix == ".json":
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
    else:
        payload = yaml.safe_load(sidecar.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("task-review sidecar must contain a mapping")
    return payload


def _declared_topology(
    payload: dict[str, Any],
) -> tuple[TopologyBasis, tuple[str, ...], tuple[tuple[str, str], ...]]:
    lifecycle = payload.get("evidence_lifecycle")
    if isinstance(lifecycle, dict) and isinstance(lifecycle.get("checkpoints"), list):
        checkpoints = lifecycle["checkpoints"]
        nodes = _declared_ids(checkpoints, identity_key="checkpoint_id", label="lifecycle checkpoint")
        lifecycle_edges = _dependency_edges(
            checkpoints,
            identity_key="checkpoint_id",
            dependency_key="depends_on",
        )
        return "evidence_lifecycle", nodes, lifecycle_edges

    stages = payload.get("stages")
    if isinstance(stages, list) and stages:
        nodes = _declared_ids(stages, identity_key="id", label="stage")
        stage_edges: list[tuple[str, str]] = []
        handoffs = payload.get("handoffs", [])
        if not isinstance(handoffs, list):
            raise ValueError("declared stage handoffs must be a list")
        for handoff in handoffs:
            if not isinstance(handoff, dict):
                raise ValueError("declared stage handoff must be a mapping")
            producer = _non_empty(handoff.get("producer_stage"))
            consumers = handoff.get("consumer_stages", [])
            if producer is None or not isinstance(consumers, list):
                raise ValueError("declared stage handoff is missing producer or consumers")
            for consumer_value in consumers:
                consumer = _non_empty(consumer_value)
                if consumer is None:
                    raise ValueError("declared stage handoff consumer must be non-empty")
                stage_edges.append((producer, consumer))
        return "stage_handoff_graph", nodes, tuple(dict.fromkeys(stage_edges))

    return "opaque_atomic", ("task",), ()


def _declared_ids(items: list[Any], *, identity_key: str, label: str) -> tuple[str, ...]:
    identities: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError(f"declared {label} must be a mapping")
        identity = _non_empty(item.get(identity_key))
        if identity is None:
            raise ValueError(f"declared {label} is missing {identity_key}")
        identities.append(identity)
    if len(identities) != len(set(identities)):
        raise ValueError(f"declared {label} ids must be unique")
    return tuple(identities)


def _dependency_edges(
    items: list[Any],
    *,
    identity_key: str,
    dependency_key: str,
) -> tuple[tuple[str, str], ...]:
    edges: list[tuple[str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("declared topology node must be a mapping")
        identity = _non_empty(item.get(identity_key))
        dependencies = item.get(dependency_key, [])
        if identity is None or not isinstance(dependencies, list):
            raise ValueError("declared topology dependencies must be a list")
        for dependency_value in dependencies:
            dependency = _non_empty(dependency_value)
            if dependency is None:
                raise ValueError("declared topology dependency must be non-empty")
            edges.append((dependency, identity))
    return tuple(edges)


def _evidence_surfaces(payload: dict[str, Any]) -> tuple[str, ...]:
    surfaces = {"task_verifier"}
    logic = payload.get("logic_profile")
    if isinstance(logic, dict) and any(
        isinstance(logic.get(key), list) and bool(logic[key])
        for key in ("closure_gates", "construction_gates", "containment_gates", "event_triggers")
    ):
        surfaces.add("logic_gates")
    for key, surface in (
        ("source_artifacts", "source_pack"),
        ("handoffs", "stage_handoffs"),
        ("deliverables", "deliverables"),
    ):
        if isinstance(payload.get(key), list) and payload[key]:
            surfaces.add(surface)
    lifecycle = payload.get("evidence_lifecycle")
    if isinstance(lifecycle, dict) and isinstance(lifecycle.get("checkpoints"), list):
        surfaces.add("lifecycle_checkpoints")
        checkpoints = lifecycle["checkpoints"]
        if any(isinstance(checkpoint, dict) and checkpoint.get("conditional_evidence") for checkpoint in checkpoints):
            surfaces.add("conditional_evidence")
        if any(isinstance(checkpoint, dict) and checkpoint.get("conditional_operations") for checkpoint in checkpoints):
            surfaces.add("conditional_operations")
    return tuple(surfaces)


def _branch_count(payload: dict[str, Any]) -> int:
    decisions = payload.get("branch_decisions")
    count = len(decisions) if isinstance(decisions, list) else 0
    lifecycle = payload.get("evidence_lifecycle")
    if isinstance(lifecycle, dict) and isinstance(lifecycle.get("checkpoints"), list):
        count += sum(
            isinstance(checkpoint, dict)
            and bool(checkpoint.get("conditional_evidence") or checkpoint.get("conditional_operations"))
            for checkpoint in lifecycle["checkpoints"]
        )
    return count


def _validate_acyclic(
    nodes: tuple[str, ...],
    edges: tuple[tuple[str, str], ...],
) -> None:
    children: dict[str, list[str]] = {node: [] for node in nodes}
    incoming: dict[str, int] = {node: 0 for node in nodes}
    for source, target in edges:
        if source not in children or target not in incoming:
            raise ValueError("declared topology edge references an unknown node")
        children[source].append(target)
        incoming[target] += 1
    ready = [node for node in nodes if incoming[node] == 0]
    visited = 0
    while ready:
        node = ready.pop()
        visited += 1
        for child in children[node]:
            incoming[child] -= 1
            if incoming[child] == 0:
                ready.append(child)
    if visited != len(nodes):
        raise ValueError("declared task topology must be acyclic")


def _non_empty(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None
