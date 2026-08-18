# ABOUTME: Tests exact unlabeled DAG identity and structural-generalization corpus boundaries.
# ABOUTME: Proves structural splits reject full or reduced isomorphism without conflating family and lineage.

from __future__ import annotations

import hashlib

import pytest
from pydantic import ValidationError

from aec_bench.contracts.run_bundle import TaskReviewSnapshotRef, TaskSnapshotRef
from aec_bench.contracts.task_definition import Visibility
from aec_bench.experimentation.proposals.structural_corpus import (
    StructuralCorpusItem,
    StructuralSplit,
    StructuralSplitManifest,
    StructuralSplitName,
    TopologyShapeRef,
    build_structural_split_manifest,
    topology_shape_ref,
)
from aec_bench.harness.compilation.task_snapshot import graph_hidden_task_snapshot_sha256


def test_renamed_and_reordered_isomorphic_dags_have_identical_signatures() -> None:
    """Names and declaration order cannot manufacture a novel graph class."""
    first = topology_shape_ref(
        nodes=("source", "left", "right", "join"),
        edges=(
            ("source", "left"),
            ("source", "right"),
            ("left", "join"),
            ("right", "join"),
        ),
    )
    renamed = topology_shape_ref(
        nodes=("z", "x", "w", "y"),
        edges=(("y", "w"), ("z", "y"), ("x", "w"), ("z", "x")),
    )

    assert first.full_signature_sha256 == renamed.full_signature_sha256
    assert first.reduced_signature_sha256 == renamed.reduced_signature_sha256
    assert first.node_count == 4
    assert first.edge_count == 4
    assert first.reduced_edge_count == 4
    assert first.depth == 3
    assert first.width == 2
    assert first.root_count == 1
    assert first.leaf_count == 1
    assert first.in_degree_multiset == (0, 1, 1, 2)
    assert first.out_degree_multiset == (0, 1, 1, 2)
    assert first.max_fan_out == 2
    assert first.max_fan_in == 2
    assert first.branch_node_count == 1
    assert first.join_node_count == 1
    assert first.full_signature_sha256 == "bbb2a244cc0cdc19a6e98c869c171a61a63e9e1cff0b6f97a63f6d32481137b8"
    assert first.reduced_signature_sha256 == "bbb2a244cc0cdc19a6e98c869c171a61a63e9e1cff0b6f97a63f6d32481137b8"
    assert first.content_sha256 == "7b4346abc308c9e5c1f200f80bc46a70bcadf879f906ce3649dfc27be7dbec9d"


def test_redundant_transitive_edge_changes_full_but_not_reduced_signature() -> None:
    """A declared shortcut remains visible even though reachability is unchanged."""
    chain = topology_shape_ref(
        nodes=("a", "b", "c"),
        edges=(("a", "b"), ("b", "c")),
    )
    shortcut = topology_shape_ref(
        nodes=("a", "b", "c"),
        edges=(("a", "b"), ("a", "c"), ("b", "c")),
    )

    assert chain.full_signature_sha256 != shortcut.full_signature_sha256
    assert chain.reduced_signature_sha256 == shortcut.reduced_signature_sha256
    assert chain.reduced_edge_count == shortcut.reduced_edge_count == 2


def test_non_isomorphic_dags_have_different_full_and_reduced_signatures() -> None:
    """A chain and a fork/join are distinct under both structural identities."""
    chain = topology_shape_ref(
        nodes=("a", "b", "c", "d"),
        edges=(("a", "b"), ("b", "c"), ("c", "d")),
    )
    diamond = topology_shape_ref(
        nodes=("a", "b", "c", "d"),
        edges=(("a", "b"), ("a", "c"), ("b", "d"), ("c", "d")),
    )

    assert chain.full_signature_sha256 != diamond.full_signature_sha256
    assert chain.reduced_signature_sha256 != diamond.reduced_signature_sha256


@pytest.mark.parametrize(
    ("nodes", "edges", "message"),
    (
        (("a", "b"), (("a", "b"), ("b", "a")), "acyclic"),
        (("a", "b"), (("a", "c"),), "declared nodes"),
        (("a", "b"), (("a", "a"),), "self edges"),
        (("a", "b"), (("a", "b"), ("a", "b")), "unique"),
    ),
)
def test_topology_shape_ref_rejects_invalid_dags(
    nodes: tuple[str, ...],
    edges: tuple[tuple[str, str], ...],
    message: str,
) -> None:
    """Malformed dependency surfaces fail before a split can be frozen."""
    with pytest.raises(ValueError, match=message):
        topology_shape_ref(nodes=nodes, edges=edges)


@pytest.mark.parametrize(
    ("metric", "impossible_value", "message"),
    (
        ("root_count", 2, "root count must match"),
        ("leaf_count", 2, "leaf count must match"),
        ("max_fan_out", 1, "maximum fan-out must match"),
        ("max_fan_in", 1, "maximum fan-in must match"),
        ("branch_node_count", 0, "branch-node count must match"),
        ("join_node_count", 0, "join-node count must match"),
    ),
)
def test_topology_shape_rejects_metrics_that_disagree_with_degree_multisets(
    metric: str,
    impossible_value: int,
    message: str,
) -> None:
    """Degree-derived metrics cannot be forged to manipulate topology distance."""
    shape = topology_shape_ref(
        nodes=("source", "left", "right", "join"),
        edges=(
            ("source", "left"),
            ("source", "right"),
            ("left", "join"),
            ("right", "join"),
        ),
    )
    payload = shape.model_dump(mode="python", exclude={"content_sha256"})
    payload[metric] = impossible_value

    with pytest.raises(ValidationError, match=message):
        TopologyShapeRef.model_validate(payload)


def test_topology_shape_preserves_metric_validation_precedence() -> None:
    """Existing structural errors precede new degree-derived consistency errors."""
    shape = topology_shape_ref(
        nodes=("source", "left", "right", "join"),
        edges=(
            ("source", "left"),
            ("source", "right"),
            ("left", "join"),
            ("right", "join"),
        ),
    )
    payload = shape.model_dump(mode="python", exclude={"content_sha256"})
    payload.update(
        {
            "in_degree_multiset": (0, 1),
            "root_count": 2,
            "leaf_count": 2,
            "max_fan_out": 1,
            "max_fan_in": 1,
            "branch_node_count": 0,
            "join_node_count": 0,
        }
    )

    with pytest.raises(ValidationError, match="in-degree multiset must contain one value per node"):
        TopologyShapeRef.model_validate(payload)


def test_manifest_rejects_cross_split_full_signature_collision() -> None:
    """Renaming a train DAG cannot place it into development."""
    train_shape = topology_shape_ref(
        nodes=("a", "b", "c"),
        edges=(("a", "b"), ("a", "c")),
    )
    renamed_shape = topology_shape_ref(
        nodes=("root", "right", "left"),
        edges=(("root", "left"), ("root", "right")),
    )

    with pytest.raises(ValidationError, match="full topology signature"):
        build_structural_split_manifest(
            manifest_id="phase9.structural.v1",
            train=_split("train", _item("train-1", "drainage", "review-train", train_shape)),
            dev=_split("dev", _item("dev-1", "roads", "review-dev", renamed_shape)),
            holdout=_split(
                "holdout",
                _chain_item(
                    "holdout-1",
                    "rail",
                    "review-holdout",
                    4,
                    visibility=Visibility.HOLDOUT,
                ),
            ),
        )


def test_manifest_rejects_cross_split_reduced_signature_collision() -> None:
    """A redundant edge cannot disguise a reachability-equivalent holdout."""
    chain = topology_shape_ref(
        nodes=("a", "b", "c"),
        edges=(("a", "b"), ("b", "c")),
    )
    shortcut = topology_shape_ref(
        nodes=("x", "y", "z"),
        edges=(("x", "y"), ("x", "z"), ("y", "z")),
    )

    with pytest.raises(ValidationError, match="reduced topology signature"):
        build_structural_split_manifest(
            manifest_id="phase9.structural.v1",
            train=_split("train", _item("train-1", "drainage", "review-train", chain)),
            dev=_split("dev", _chain_item("dev-1", "roads", "review-dev", 4)),
            holdout=_split(
                "holdout",
                _item(
                    "holdout-1",
                    "drainage",
                    "review-holdout",
                    shortcut,
                    visibility=Visibility.HOLDOUT,
                ),
            ),
        )


def test_manifest_keeps_family_and_review_lineage_separate_and_records_distance() -> None:
    """A family may recur on novel structures while every review lineage remains independent."""
    train = _split("train", _chain_item("train-1", "drainage", "review-train", 3))
    dev = _split("dev", _chain_item("dev-1", "roads", "review-dev", 4))
    holdout = _split(
        "holdout",
        _item(
            "holdout-1",
            "drainage",
            "review-holdout",
            topology_shape_ref(
                nodes=("r", "a", "b", "c", "j"),
                edges=(("r", "a"), ("r", "b"), ("r", "c"), ("a", "j"), ("b", "j"), ("c", "j")),
            ),
            visibility=Visibility.HOLDOUT,
        ),
    )

    manifest = build_structural_split_manifest(
        manifest_id="phase9.structural.v1",
        train=train,
        dev=dev,
        holdout=holdout,
    )

    assert manifest.train.items[0].semantic_family == "drainage"
    assert manifest.holdout.items[0].semantic_family == "drainage"
    assert manifest.train.items[0].review_lineage_id != manifest.holdout.items[0].review_lineage_id
    assert manifest.train.items[0].visibility is Visibility.PUBLIC
    assert manifest.holdout.items[0].visibility is Visibility.HOLDOUT
    assert manifest.train.items[0].snapshot.task_id == "train-1"
    assert {(item.left_split, item.right_split) for item in manifest.near_structure_distances} == {
        ("train", "dev"),
        ("train", "holdout"),
        ("dev", "holdout"),
    }
    assert all(item.metric_l1_distance >= 0 for item in manifest.near_structure_distances)
    assert len(manifest.content_sha256) == 64


def test_task_manifest_projection_binds_exact_public_and_sealed_packages_not_manifest_label() -> None:
    """EvaluationPlan gets a stable exact task-set identity distinct from split-manifest identity."""
    manifest = build_structural_split_manifest(
        manifest_id="phase9.structural.v1",
        train=_split("train", _chain_item("train-1", "drainage", "review-train", 3)),
        dev=_split("dev", _chain_item("dev-1", "roads", "review-dev", 4)),
        holdout=_split(
            "holdout",
            _chain_item(
                "holdout-1",
                "rail",
                "review-holdout",
                5,
                visibility=Visibility.HOLDOUT,
            ),
        ),
    )
    relabelled = manifest.model_copy(update={"manifest_id": "phase9.structural.relabelled"})

    assert len(manifest.task_manifest_sha256) == 64
    assert relabelled.task_manifest_sha256 == manifest.task_manifest_sha256
    changed_public = manifest.model_copy(
        update={
            "train": manifest.train.model_copy(
                update={
                    "items": (
                        manifest.train.items[0].model_copy(
                            update={
                                "public_snapshot": manifest.train.items[0].public_snapshot.model_copy(
                                    update={"package_sha256": _digest("changed-public-package")}
                                )
                            }
                        ),
                    )
                }
            )
        }
    )
    assert changed_public.task_manifest_sha256 != manifest.task_manifest_sha256


def test_manifest_rejects_reused_task_or_world_identity() -> None:
    """Task package and review lineage identities are globally independent across splits."""
    train = _split("train", _chain_item("same-task", "drainage", "same-review", 3))
    dev = _split("dev", _chain_item("same-task", "roads", "review-dev", 4))
    holdout = _split(
        "holdout",
        _chain_item(
            "holdout-1",
            "rail",
            "same-review",
            5,
            visibility=Visibility.HOLDOUT,
        ),
    )

    with pytest.raises(ValidationError, match="task identities must be unique"):
        StructuralSplitManifest(
            manifest_id="phase9.structural.v1",
            train=train,
            dev=dev,
            holdout=holdout,
            near_structure_distances=(),
        )

    dev = _split("dev", _chain_item("dev-1", "roads", "review-dev", 4))
    with pytest.raises(ValidationError, match="review lineage identities must be unique"):
        StructuralSplitManifest(
            manifest_id="phase9.structural.v1",
            train=train,
            dev=dev,
            holdout=holdout,
            near_structure_distances=(),
        )


def test_item_rejects_snapshot_lineage_and_visibility_mismatches() -> None:
    """Every descriptive identity must agree with the exact host-owned task snapshot."""
    shape = topology_shape_ref(nodes=("a", "b"), edges=(("a", "b"),))
    valid = _item("train-1", "drainage", "review-train", shape)

    with pytest.raises(ValidationError, match="public snapshot task id"):
        StructuralCorpusItem.model_validate(
            {
                **valid.model_dump(mode="python"),
                "public_snapshot": valid.public_snapshot.model_copy(update={"task_id": "other-task"}),
            }
        )

    with pytest.raises(ValidationError, match="snapshot task id"):
        StructuralCorpusItem.model_validate(
            {
                **valid.model_dump(mode="python"),
                "snapshot": valid.snapshot.model_copy(update={"task_id": "other-task"}),
            }
        )

    with pytest.raises(ValidationError, match="review lineage"):
        StructuralCorpusItem.model_validate(
            {
                **valid.model_dump(mode="python"),
                "review_lineage_id": _digest("different-review"),
            }
        )

    with pytest.raises(ValidationError, match="task-review visibility"):
        StructuralCorpusItem.model_validate(
            {
                **valid.model_dump(mode="python"),
                "visibility": Visibility.HOLDOUT,
            }
        )

    with pytest.raises(ValidationError, match="public snapshot cannot contain"):
        StructuralCorpusItem.model_validate(
            {
                **valid.model_dump(mode="python"),
                "public_snapshot": valid.public_snapshot.model_copy(update={"task_review": valid.snapshot.task_review}),
            }
        )

    with pytest.raises(ValidationError, match="definition identities must match"):
        StructuralCorpusItem.model_validate(
            {
                **valid.model_dump(mode="python"),
                "public_snapshot": valid.public_snapshot.model_copy(
                    update={"definition_sha256": _digest("different-definition")}
                ),
            }
        )

    with pytest.raises(ValidationError, match="physically distinct"):
        StructuralCorpusItem.model_validate(
            {
                **valid.model_dump(mode="python"),
                "public_snapshot": valid.public_snapshot.model_copy(
                    update={"package_sha256": valid.snapshot.package_sha256}
                ),
            }
        )


def test_item_derives_the_exact_graph_hidden_public_snapshot_identity() -> None:
    """The safe proposer view can be joined exactly to its host-owned corpus item."""
    item = _chain_item("train-1", "drainage", "review-train", 3)

    assert item.public_task_snapshot_sha256 == graph_hidden_task_snapshot_sha256(item.public_snapshot)


def test_manifest_enforces_split_visibility() -> None:
    """Development data is public and sealed structural holdout data is holdout."""
    with pytest.raises(ValidationError, match="dev structural split visibility must be public"):
        _split(
            "dev",
            _chain_item(
                "dev-1",
                "roads",
                "review-dev",
                4,
                visibility=Visibility.HOLDOUT,
            ),
        )


def test_manifest_rejects_duplicate_task_packages() -> None:
    """Renaming a task cannot make duplicate task-package bytes independent."""
    train_item = _chain_item("train-1", "drainage", "review-train", 3)
    dev_item = _chain_item("dev-1", "roads", "review-dev", 4)
    holdout_item = _chain_item(
        "holdout-1",
        "rail",
        "review-holdout",
        5,
        visibility=Visibility.HOLDOUT,
    )

    duplicate_package_dev = dev_item.model_copy(
        update={"snapshot": dev_item.snapshot.model_copy(update={"package_sha256": train_item.snapshot.package_sha256})}
    )
    with pytest.raises(ValidationError, match="package snapshots must be unique"):
        StructuralSplitManifest(
            manifest_id="phase9.structural.v1",
            train=_split("train", train_item),
            dev=_split("dev", duplicate_package_dev),
            holdout=_split("holdout", holdout_item),
            near_structure_distances=(),
        )

    duplicate_public_package_dev = dev_item.model_copy(
        update={
            "public_snapshot": dev_item.public_snapshot.model_copy(
                update={"package_sha256": train_item.public_snapshot.package_sha256}
            )
        }
    )
    with pytest.raises(ValidationError, match="public task package snapshots must be unique"):
        StructuralSplitManifest(
            manifest_id="phase9.structural.v1",
            train=_split("train", train_item),
            dev=_split("dev", duplicate_public_package_dev),
            holdout=_split("holdout", holdout_item),
            near_structure_distances=(),
        )


def _split(split: StructuralSplitName, *items: StructuralCorpusItem) -> StructuralSplit:
    return StructuralSplit(split=split, items=items)


def _item(
    task_id: str,
    family: str,
    lineage: str,
    shape: TopologyShapeRef,
    *,
    visibility: Visibility = Visibility.PUBLIC,
) -> StructuralCorpusItem:
    lineage_sha256 = _digest(lineage)
    return StructuralCorpusItem(
        task_id=task_id,
        semantic_family=family,
        review_lineage_id=lineage_sha256,
        visibility=visibility,
        public_snapshot=TaskSnapshotRef(
            task_id=task_id,
            definition_sha256=_digest(f"definition:{task_id}"),
            package_sha256=_digest(f"public-package:{task_id}"),
        ),
        snapshot=TaskSnapshotRef(
            task_id=task_id,
            definition_sha256=_digest(f"definition:{task_id}"),
            package_sha256=_digest(f"sealed-package:{task_id}"),
            task_review=TaskReviewSnapshotRef(
                profile_id=f"review:{task_id}",
                review_profile_sha256=_digest(f"review-profile:{task_id}"),
                review_sidecar_sha256=lineage_sha256,
                declared_surface_sha256=_digest(f"declared-surface:{task_id}"),
                visibility=visibility,
            ),
        ),
        topology=shape,
    )


def _chain_item(
    task_id: str,
    family: str,
    lineage: str,
    node_count: int,
    *,
    visibility: Visibility = Visibility.PUBLIC,
) -> StructuralCorpusItem:
    nodes = tuple(f"n{index}" for index in range(node_count))
    return _item(
        task_id,
        family,
        lineage,
        topology_shape_ref(
            nodes=nodes,
            edges=tuple((nodes[index], nodes[index + 1]) for index in range(node_count - 1)),
        ),
        visibility=visibility,
    )


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
