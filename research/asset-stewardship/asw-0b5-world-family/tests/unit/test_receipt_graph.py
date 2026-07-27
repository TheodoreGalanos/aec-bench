# ABOUTME: Specifies the B5-W0 common receipt envelope, content identity, and graph rejection boundary.
# ABOUTME: Covers graph structure only and does not implement package promotion or later B5 stage semantics.

from __future__ import annotations

from dataclasses import replace

import pytest
from asw_b5_lineage import receipts
from support import canonical_bytes, digest, receipt_envelope

GENERATION_ID = digest("generation")


def parsed_receipt(
    *,
    kind: str = "generation-declaration",
    parents: tuple[str, ...] = (),
    generation_id: str = GENERATION_ID,
    profile_id: str = "AU-NSW-LH-SYN-SPS-v1",
) -> receipts.IdentifiedReceipt:
    return receipts.read_receipt(
        canonical_bytes(
            receipt_envelope(
                generation_id=generation_id,
                kind=kind,
                parents=parents,
                profile_id=profile_id,
            )
        )
    )


def test_receipt_identity_binds_kind_and_canonical_envelope() -> None:
    receipt = parsed_receipt()

    assert receipt.receipt_id == receipts.receipt_id(
        receipt.envelope["receipt_kind"],
        receipt.canonical_bytes,
    )
    assert len(receipt.receipt_id) == 64
    assert receipt.receipt_id.islower()


def test_accepts_connected_stage_ordered_receipt_graph() -> None:
    root = parsed_receipt()
    engine = parsed_receipt(kind="engine-build", parents=(root.receipt_id,))
    candidate = parsed_receipt(
        kind="generator-case",
        parents=(root.receipt_id, engine.receipt_id),
    )

    receipts.validate_receipt_graph((root, engine, candidate))


def test_rejects_missing_duplicate_and_unknown_parents() -> None:
    root = parsed_receipt()
    missing = parsed_receipt(
        kind="engine-build",
        parents=(digest("missing-parent"),),
    )
    duplicate_parent = parsed_receipt(
        kind="engine-build",
        parents=(root.receipt_id, root.receipt_id),
    )

    with pytest.raises(receipts.ReceiptBoundaryError, match="graph.missing-parent"):
        receipts.validate_receipt_graph((root, missing))
    with pytest.raises(
        receipts.ReceiptBoundaryError,
        match="graph.duplicate-parent",
    ):
        receipts.validate_receipt_graph((root, duplicate_parent))
    with pytest.raises(receipts.ReceiptBoundaryError, match="graph.duplicate-receipt"):
        receipts.validate_receipt_graph((root, root))


def test_rejects_cycle_before_graph_use() -> None:
    root = parsed_receipt()
    left = parsed_receipt(kind="engine-build", parents=(digest("right"),))
    right = parsed_receipt(kind="generator-case", parents=(digest("left"),))
    left = replace(left, receipt_id=digest("left"))
    right = replace(right, receipt_id=digest("right"))

    with pytest.raises(receipts.ReceiptBoundaryError, match="graph.cycle"):
        receipts.validate_receipt_graph((root, left, right))


def test_rejects_wrong_profile_generation_and_stage_direction() -> None:
    root = parsed_receipt()
    wrong_profile = parsed_receipt(
        kind="engine-build",
        parents=(root.receipt_id,),
        profile_id="AU-NSW-LH-SYN-SPS-v2",
    )
    wrong_generation = parsed_receipt(
        kind="engine-build",
        parents=(root.receipt_id,),
        generation_id=digest("other-generation"),
    )
    backwards_parent = parsed_receipt(
        kind="engine-build",
        parents=(digest("later-receipt"),),
    )
    later = parsed_receipt(
        kind="generator-case",
        parents=(root.receipt_id,),
    )
    later = replace(later, receipt_id=digest("later-receipt"))

    with pytest.raises(receipts.ReceiptBoundaryError, match="graph.profile"):
        receipts.validate_receipt_graph((root, wrong_profile))
    with pytest.raises(receipts.ReceiptBoundaryError, match="graph.generation"):
        receipts.validate_receipt_graph((root, wrong_generation))
    with pytest.raises(receipts.ReceiptBoundaryError, match="graph.stage-order"):
        receipts.validate_receipt_graph((root, backwards_parent, later))


def test_rejects_unknown_kind_and_unowned_promotable_state() -> None:
    unknown = receipt_envelope(generation_id=GENERATION_ID)
    unknown["receipt_kind"] = "mystery-receipt"
    with pytest.raises(receipts.ReceiptBoundaryError, match="receipt.kind"):
        receipts.read_receipt(canonical_bytes(unknown))

    promotable = receipt_envelope(generation_id=GENERATION_ID)
    promotable["promotable"] = True
    with pytest.raises(receipts.ReceiptBoundaryError, match="receipt.promotable"):
        receipts.read_receipt(canonical_bytes(promotable))
