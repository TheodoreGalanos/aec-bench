# ABOUTME: Defines exact unlabeled DAG identities for structural-generalization corpora.
# ABOUTME: Freezes leakage-resistant train, development, and holdout topology splits.

from __future__ import annotations

from itertools import combinations, permutations
from typing import Literal, Self

from pydantic import Field, NonNegativeInt, PositiveInt, field_validator, model_validator

from aec_bench.contracts.harness_kernel import (
    ContentAddressedModel,
    FrozenStrictModel,
    canonical_content_sha256,
    validate_sha256,
)
from aec_bench.contracts.run_bundle import TaskSnapshotRef
from aec_bench.contracts.task_definition import Visibility
from aec_bench.contracts.validators import NonEmptyStr
from aec_bench.meta_harness.adaptive_cycle_corpus import TaskGenerationIdentity
from aec_bench.meta_harness.task_snapshot import graph_hidden_task_snapshot_sha256

StructuralSplitName = Literal["train", "dev", "holdout"]
DirectedEdge = tuple[str, str]


class TopologyShapeRef(ContentAddressedModel):
    """Name-independent identity and descriptive metrics for one dependency DAG."""

    schema_version: Literal["aecbench.topology-shape.v1"] = "aecbench.topology-shape.v1"
    full_signature_sha256: str
    reduced_signature_sha256: str
    node_count: PositiveInt
    edge_count: NonNegativeInt
    reduced_edge_count: NonNegativeInt
    depth: PositiveInt
    width: PositiveInt
    root_count: PositiveInt
    leaf_count: PositiveInt
    in_degree_multiset: tuple[NonNegativeInt, ...]
    out_degree_multiset: tuple[NonNegativeInt, ...]
    max_fan_out: NonNegativeInt
    max_fan_in: NonNegativeInt
    branch_node_count: NonNegativeInt
    join_node_count: NonNegativeInt

    @field_validator("full_signature_sha256", "reduced_signature_sha256")
    @classmethod
    def validate_signature(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_metrics(self) -> Self:
        _validate_topology_degree_shape(self)
        _validate_topology_edge_accounting(self)
        _validate_topology_metric_bounds(self)
        _validate_topology_degree_metrics(self)
        return self


def _validate_topology_degree_shape(shape: TopologyShapeRef) -> None:
    if shape.node_count > 8:
        raise ValueError("topology shapes support at most 8 nodes")
    if len(shape.in_degree_multiset) != shape.node_count:
        raise ValueError("in-degree multiset must contain one value per node")
    if len(shape.out_degree_multiset) != shape.node_count:
        raise ValueError("out-degree multiset must contain one value per node")
    if tuple(sorted(shape.in_degree_multiset)) != shape.in_degree_multiset:
        raise ValueError("in-degree multiset must be sorted")
    if tuple(sorted(shape.out_degree_multiset)) != shape.out_degree_multiset:
        raise ValueError("out-degree multiset must be sorted")


def _validate_topology_edge_accounting(shape: TopologyShapeRef) -> None:
    if sum(shape.in_degree_multiset) != shape.edge_count:
        raise ValueError("in-degree multiset must account for every edge")
    if sum(shape.out_degree_multiset) != shape.edge_count:
        raise ValueError("out-degree multiset must account for every edge")
    if shape.reduced_edge_count > shape.edge_count:
        raise ValueError("transitive reduction cannot contain more edges than the full DAG")


def _validate_topology_metric_bounds(shape: TopologyShapeRef) -> None:
    if shape.depth > shape.node_count or shape.width > shape.node_count:
        raise ValueError("topology depth and width cannot exceed its node count")
    if shape.root_count > shape.node_count or shape.leaf_count > shape.node_count:
        raise ValueError("topology root and leaf counts cannot exceed its node count")


def _validate_topology_degree_metrics(shape: TopologyShapeRef) -> None:
    expected_metrics = (
        (
            shape.root_count,
            sum(degree == 0 for degree in shape.in_degree_multiset),
            "topology root count must match zero in-degree entries",
        ),
        (
            shape.leaf_count,
            sum(degree == 0 for degree in shape.out_degree_multiset),
            "topology leaf count must match zero out-degree entries",
        ),
        (
            shape.max_fan_out,
            max(shape.out_degree_multiset),
            "topology maximum fan-out must match its out-degree multiset",
        ),
        (
            shape.max_fan_in,
            max(shape.in_degree_multiset),
            "topology maximum fan-in must match its in-degree multiset",
        ),
        (
            shape.branch_node_count,
            sum(degree > 1 for degree in shape.out_degree_multiset),
            "topology branch-node count must match out-degree entries above one",
        ),
        (
            shape.join_node_count,
            sum(degree > 1 for degree in shape.in_degree_multiset),
            "topology join-node count must match in-degree entries above one",
        ),
    )
    for actual, expected, message in expected_metrics:
        if actual != expected:
            raise ValueError(message)


class StructuralCorpusItem(FrozenStrictModel):
    """One task/world observation with graph structure kept separate from semantics."""

    task_id: NonEmptyStr
    semantic_family: NonEmptyStr
    world_lineage_id: NonEmptyStr
    visibility: Visibility
    public_snapshot: TaskSnapshotRef
    snapshot: TaskSnapshotRef
    generation_identity: TaskGenerationIdentity
    topology: TopologyShapeRef

    @field_validator("world_lineage_id")
    @classmethod
    def validate_world_lineage(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_host_bindings(self) -> Self:
        if self.public_snapshot.task_id != self.task_id:
            raise ValueError("structural corpus item public snapshot task id must match its task id")
        if self.snapshot.task_id != self.task_id:
            raise ValueError("structural corpus item snapshot task id must match its task id")
        if self.generation_identity.task_id != self.task_id:
            raise ValueError("structural corpus item generation identity task id must match its task id")
        if self.public_snapshot.world is not None:
            raise ValueError("structural corpus item public snapshot cannot contain a task world")
        if self.snapshot.world is None:
            raise ValueError("structural corpus item snapshot must include a task world")
        if self.public_snapshot.definition_sha256 != self.snapshot.definition_sha256:
            raise ValueError("public and sealed task definition identities must match")
        if self.public_snapshot.package_sha256 == self.snapshot.package_sha256:
            raise ValueError("public and sealed task packages must be physically distinct")
        if self.world_lineage_id != self.snapshot.world.world_package_sha256:
            raise ValueError("structural corpus item world lineage must match snapshot world bytes")
        if self.visibility is not self.snapshot.world.visibility:
            raise ValueError("structural corpus item snapshot world visibility must match item visibility")
        return self

    @property
    def public_task_snapshot_sha256(self) -> str:
        """Return the exact safe task-package identity exposed through the problem view."""
        return graph_hidden_task_snapshot_sha256(self.public_snapshot)


class StructuralSplit(FrozenStrictModel):
    """One named structural evidence split."""

    split: StructuralSplitName
    items: tuple[StructuralCorpusItem, ...] = Field(min_length=1)

    @field_validator("items")
    @classmethod
    def canonicalize_items(
        cls,
        value: tuple[StructuralCorpusItem, ...],
    ) -> tuple[StructuralCorpusItem, ...]:
        return tuple(sorted(value, key=lambda item: item.task_id))

    @model_validator(mode="after")
    def validate_local_identities(self) -> Self:
        expected_visibility = Visibility.HOLDOUT if self.split == "holdout" else Visibility.PUBLIC
        if any(item.visibility is not expected_visibility for item in self.items):
            raise ValueError(f"{self.split} structural split visibility must be {expected_visibility.value}")
        task_ids = tuple(item.task_id for item in self.items)
        if len(task_ids) != len(set(task_ids)):
            raise ValueError("structural split task identities must be unique")
        lineage_ids = tuple(item.world_lineage_id for item in self.items)
        if len(lineage_ids) != len(set(lineage_ids)):
            raise ValueError("structural split world lineage identities must be unique")
        return self


class NearStructureDistance(FrozenStrictModel):
    """Descriptive metric distance between two cross-split topology observations."""

    left_split: StructuralSplitName
    left_task_id: NonEmptyStr
    left_full_signature_sha256: str
    right_split: StructuralSplitName
    right_task_id: NonEmptyStr
    right_full_signature_sha256: str
    metric_l1_distance: NonNegativeInt

    @field_validator("left_full_signature_sha256", "right_full_signature_sha256")
    @classmethod
    def validate_signature(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_order(self) -> Self:
        split_order = {"train": 0, "dev": 1, "holdout": 2}
        if split_order[self.left_split] >= split_order[self.right_split]:
            raise ValueError("near-structure distances must follow train, dev, holdout order")
        return self


class StructuralSplitManifest(ContentAddressedModel):
    """Immutable structural split with exact full and reduced isomorphism exclusion."""

    schema_version: Literal["aecbench.structural-split.v1"] = "aecbench.structural-split.v1"
    manifest_id: NonEmptyStr
    train: StructuralSplit
    dev: StructuralSplit
    holdout: StructuralSplit
    near_structure_distances: tuple[NearStructureDistance, ...]

    @field_validator("near_structure_distances")
    @classmethod
    def canonicalize_distances(
        cls,
        value: tuple[NearStructureDistance, ...],
    ) -> tuple[NearStructureDistance, ...]:
        return tuple(
            sorted(
                value,
                key=lambda item: (
                    item.left_split,
                    item.right_split,
                    item.left_task_id,
                    item.right_task_id,
                ),
            )
        )

    @model_validator(mode="after")
    def validate_split_boundary(self) -> Self:
        if self.train.split != "train" or self.dev.split != "dev" or self.holdout.split != "holdout":
            raise ValueError("structural manifest fields must use their named evidence splits")

        splits = (self.train, self.dev, self.holdout)
        items = tuple(item for split in splits for item in split.items)
        task_ids = tuple(item.task_id for item in items)
        if len(task_ids) != len(set(task_ids)):
            raise ValueError("structural manifest task identities must be unique across splits")
        lineage_ids = tuple(item.world_lineage_id for item in items)
        if len(lineage_ids) != len(set(lineage_ids)):
            raise ValueError("structural manifest world lineage identities must be unique across splits")
        package_hashes = tuple(item.snapshot.package_sha256 for item in items)
        if len(package_hashes) != len(set(package_hashes)):
            raise ValueError("structural manifest task package snapshots must be unique")
        public_package_hashes = tuple(item.public_snapshot.package_sha256 for item in items)
        if len(public_package_hashes) != len(set(public_package_hashes)):
            raise ValueError("structural manifest public task package snapshots must be unique")
        generation_keys = tuple(
            (
                item.generation_identity.template,
                item.generation_identity.template_source_sha256,
                item.generation_identity.seed,
                item.generation_identity.instance_index,
            )
            for item in items
        )
        if len(generation_keys) != len(set(generation_keys)):
            raise ValueError("structural manifest generation identities must be unique")

        _reject_cross_split_signature_collision(
            splits,
            attribute="full_signature_sha256",
            label="full topology signature",
        )
        _reject_cross_split_signature_collision(
            splits,
            attribute="reduced_signature_sha256",
            label="reduced topology signature",
        )

        expected_distances = _cross_split_distances(splits)
        if self.near_structure_distances != expected_distances:
            raise ValueError("near-structure distances must be the complete descriptive cross-split metric set")
        return self

    @property
    def task_manifest_sha256(self) -> str:
        """Project exact task/world package identities separately from topology split policy."""
        return canonical_content_sha256(
            {
                "schema_version": "aecbench.structural-task-manifest-projection.v1",
                "items": [
                    {
                        "split": split.split,
                        "task_id": item.task_id,
                        "semantic_family": item.semantic_family,
                        "world_lineage_id": item.world_lineage_id,
                        "visibility": item.visibility.value,
                        "public_snapshot": item.public_snapshot.model_dump(mode="json"),
                        "sealed_snapshot": item.snapshot.model_dump(mode="json"),
                        "generation_identity": item.generation_identity.model_dump(mode="json"),
                    }
                    for split in (self.train, self.dev, self.holdout)
                    for item in split.items
                ],
            }
        )


def topology_shape_ref(
    *,
    nodes: tuple[str, ...],
    edges: tuple[DirectedEdge, ...],
) -> TopologyShapeRef:
    """Build an exact name-independent identity for a bounded dependency DAG."""
    normalized_nodes, indexed_edges = _validate_dag(nodes=nodes, edges=edges)
    node_count = len(normalized_nodes)
    reduced_edges = _transitive_reduction(node_count=node_count, edges=indexed_edges)
    in_degrees, out_degrees = _degrees(node_count=node_count, edges=indexed_edges)
    reachability = _reachability(node_count=node_count, edges=indexed_edges)

    return TopologyShapeRef(
        full_signature_sha256=_canonical_unlabeled_signature(
            node_count=node_count,
            edges=indexed_edges,
        ),
        reduced_signature_sha256=_canonical_unlabeled_signature(
            node_count=node_count,
            edges=reduced_edges,
        ),
        node_count=node_count,
        edge_count=len(indexed_edges),
        reduced_edge_count=len(reduced_edges),
        depth=_dag_depth(node_count=node_count, edges=indexed_edges),
        width=_dag_width(node_count=node_count, reachability=reachability),
        root_count=sum(degree == 0 for degree in in_degrees),
        leaf_count=sum(degree == 0 for degree in out_degrees),
        in_degree_multiset=tuple(sorted(in_degrees)),
        out_degree_multiset=tuple(sorted(out_degrees)),
        max_fan_out=max(out_degrees),
        max_fan_in=max(in_degrees),
        branch_node_count=sum(degree > 1 for degree in out_degrees),
        join_node_count=sum(degree > 1 for degree in in_degrees),
    )


def build_structural_split_manifest(
    *,
    manifest_id: str,
    train: StructuralSplit,
    dev: StructuralSplit,
    holdout: StructuralSplit,
) -> StructuralSplitManifest:
    """Freeze exact splits and their descriptive, non-gating structure distances."""
    splits = (train, dev, holdout)
    return StructuralSplitManifest(
        manifest_id=manifest_id,
        train=train,
        dev=dev,
        holdout=holdout,
        near_structure_distances=_cross_split_distances(splits),
    )


def _validate_dag(
    *,
    nodes: tuple[str, ...],
    edges: tuple[DirectedEdge, ...],
) -> tuple[tuple[str, ...], frozenset[tuple[int, int]]]:
    if not nodes:
        raise ValueError("topology DAG must contain at least one node")
    if len(nodes) > 8:
        raise ValueError("topology DAG must contain at most 8 nodes")
    if any(not node.strip() for node in nodes):
        raise ValueError("topology DAG node names must not be blank")
    if len(nodes) != len(set(nodes)):
        raise ValueError("topology DAG node names must be unique")
    if len(edges) != len(set(edges)):
        raise ValueError("topology DAG edges must be unique")

    node_indexes = {node: index for index, node in enumerate(nodes)}
    indexed_edges: set[tuple[int, int]] = set()
    for source, target in edges:
        if source not in node_indexes or target not in node_indexes:
            raise ValueError("topology DAG edges must reference declared nodes")
        if source == target:
            raise ValueError("topology DAG must not contain self edges")
        indexed_edges.add((node_indexes[source], node_indexes[target]))

    frozen_edges = frozenset(indexed_edges)
    if len(_topological_order(node_count=len(nodes), edges=frozen_edges)) != len(nodes):
        raise ValueError("topology graph must be acyclic")
    return nodes, frozen_edges


def _topological_order(
    *,
    node_count: int,
    edges: frozenset[tuple[int, int]],
) -> tuple[int, ...]:
    incoming = [0] * node_count
    outgoing: list[list[int]] = [[] for _ in range(node_count)]
    for source, target in edges:
        incoming[target] += 1
        outgoing[source].append(target)

    ready = sorted(index for index, degree in enumerate(incoming) if degree == 0)
    ordered: list[int] = []
    while ready:
        node = ready.pop(0)
        ordered.append(node)
        for target in sorted(outgoing[node]):
            incoming[target] -= 1
            if incoming[target] == 0:
                ready.append(target)
                ready.sort()
    return tuple(ordered)


def _canonical_unlabeled_signature(
    *,
    node_count: int,
    edges: frozenset[tuple[int, int]],
) -> str:
    canonical_bits = min(
        "".join(
            "1" if (ordering[source], ordering[target]) in edges else "0"
            for source in range(node_count)
            for target in range(node_count)
        )
        for ordering in permutations(range(node_count))
    )
    return canonical_content_sha256(
        {
            "kind": "unlabeled_directed_graph",
            "node_count": node_count,
            "adjacency_bits": canonical_bits,
        }
    )


def _transitive_reduction(
    *,
    node_count: int,
    edges: frozenset[tuple[int, int]],
) -> frozenset[tuple[int, int]]:
    reduced = {
        edge
        for edge in edges
        if not _path_exists(
            start=edge[0],
            target=edge[1],
            edges=edges - {edge},
            node_count=node_count,
        )
    }
    return frozenset(reduced)


def _path_exists(
    *,
    start: int,
    target: int,
    edges: frozenset[tuple[int, int]],
    node_count: int,
) -> bool:
    outgoing: list[list[int]] = [[] for _ in range(node_count)]
    for source, destination in edges:
        outgoing[source].append(destination)
    frontier = [start]
    visited = {start}
    while frontier:
        node = frontier.pop()
        for destination in outgoing[node]:
            if destination == target:
                return True
            if destination not in visited:
                visited.add(destination)
                frontier.append(destination)
    return False


def _degrees(
    *,
    node_count: int,
    edges: frozenset[tuple[int, int]],
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    incoming = [0] * node_count
    outgoing = [0] * node_count
    for source, target in edges:
        outgoing[source] += 1
        incoming[target] += 1
    return tuple(incoming), tuple(outgoing)


def _reachability(
    *,
    node_count: int,
    edges: frozenset[tuple[int, int]],
) -> tuple[frozenset[int], ...]:
    return tuple(
        frozenset(
            target
            for target in range(node_count)
            if target != source
            and _path_exists(
                start=source,
                target=target,
                edges=edges,
                node_count=node_count,
            )
        )
        for source in range(node_count)
    )


def _dag_depth(
    *,
    node_count: int,
    edges: frozenset[tuple[int, int]],
) -> int:
    outgoing: list[list[int]] = [[] for _ in range(node_count)]
    for source, target in edges:
        outgoing[source].append(target)
    depth = [1] * node_count
    for source in _topological_order(node_count=node_count, edges=edges):
        for target in outgoing[source]:
            depth[target] = max(depth[target], depth[source] + 1)
    return max(depth)


def _dag_width(
    *,
    node_count: int,
    reachability: tuple[frozenset[int], ...],
) -> int:
    for size in range(node_count, 0, -1):
        for candidate in combinations(range(node_count), size):
            if all(
                right not in reachability[left] and left not in reachability[right]
                for left, right in combinations(candidate, 2)
            ):
                return size
    raise AssertionError("a non-empty DAG always has an antichain")


def _reject_cross_split_signature_collision(
    splits: tuple[StructuralSplit, StructuralSplit, StructuralSplit],
    *,
    attribute: Literal["full_signature_sha256", "reduced_signature_sha256"],
    label: str,
) -> None:
    for left_index, left in enumerate(splits):
        left_signatures = {getattr(item.topology, attribute) for item in left.items}
        for right in splits[left_index + 1 :]:
            right_signatures = {getattr(item.topology, attribute) for item in right.items}
            if left_signatures.intersection(right_signatures):
                raise ValueError(f"{label} must not collide across {left.split} and {right.split} splits")


def _cross_split_distances(
    splits: tuple[StructuralSplit, StructuralSplit, StructuralSplit],
) -> tuple[NearStructureDistance, ...]:
    distances = tuple(
        NearStructureDistance(
            left_split=left.split,
            left_task_id=left_item.task_id,
            left_full_signature_sha256=left_item.topology.full_signature_sha256,
            right_split=right.split,
            right_task_id=right_item.task_id,
            right_full_signature_sha256=right_item.topology.full_signature_sha256,
            metric_l1_distance=_metric_l1_distance(left_item.topology, right_item.topology),
        )
        for left_index, left in enumerate(splits)
        for right in splits[left_index + 1 :]
        for left_item in left.items
        for right_item in right.items
    )
    return tuple(
        sorted(
            distances,
            key=lambda item: (
                item.left_split,
                item.right_split,
                item.left_task_id,
                item.right_task_id,
            ),
        )
    )


def _metric_l1_distance(left: TopologyShapeRef, right: TopologyShapeRef) -> int:
    left_vector = _metric_vector(left)
    right_vector = _metric_vector(right)
    return sum(abs(left_value - right_value) for left_value, right_value in zip(left_vector, right_vector, strict=True))


def _metric_vector(shape: TopologyShapeRef) -> tuple[int, ...]:
    padded_in_degrees = shape.in_degree_multiset + (0,) * (8 - shape.node_count)
    padded_out_degrees = shape.out_degree_multiset + (0,) * (8 - shape.node_count)
    return (
        shape.node_count,
        shape.edge_count,
        shape.reduced_edge_count,
        shape.depth,
        shape.width,
        shape.root_count,
        shape.leaf_count,
        shape.max_fan_out,
        shape.max_fan_in,
        shape.branch_node_count,
        shape.join_node_count,
        *padded_in_degrees,
        *padded_out_degrees,
    )
