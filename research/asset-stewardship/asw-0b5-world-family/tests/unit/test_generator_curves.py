# ABOUTME: Specifies the W2 33-point PUMP3 curve compiler and deterministic decimal quantization.
# ABOUTME: Protects exact endpoints, monotonicity, label symmetry, and mechanism-state ownership.

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from generator import curves, request

B5_ROOT = Path(__file__).parents[2]
W1_DECLARATION = B5_ROOT / "declarations" / "w1-member-authority.json"


def test_clean_curve_has_exact_endpoints_order_and_point_count() -> None:
    member = request.anchor_member(W1_DECLARATION.read_bytes())

    points = curves.materialize(member, obstruction="0", clearance_loss="0")

    assert len(points) == 33
    assert points[0].head_m == Decimal("0.000000000")
    assert points[0].flow_lps > Decimal("0.000000")
    assert points[-1].head_m == Decimal("18.500000000")
    assert points[-1].flow_lps == Decimal("0.000000")
    assert all(
        left.head_m < right.head_m
        for left, right in zip(points, points[1:], strict=False)
    )
    assert all(
        left.flow_lps >= right.flow_lps
        for left, right in zip(points, points[1:], strict=False)
    )


def test_mechanisms_reduce_support_and_matched_labels_hash_identically() -> None:
    member = request.anchor_member(W1_DECLARATION.read_bytes())

    clean = curves.materialize(member, obstruction="0", clearance_loss="0")
    degraded = curves.materialize(member, obstruction="0.75", clearance_loss="0")

    assert degraded[0].flow_lps < clean[0].flow_lps
    assert degraded[-1].head_m < clean[-1].head_m
    assert curves.curve_sha256(clean) == curves.curve_sha256(
        curves.materialize(member, obstruction="0", clearance_loss="0")
    )
    assert curves.canonical_curve_bytes(clean).endswith(b"\n")


def test_net_head_curve_subtracts_full_system_loss_and_has_separate_identity() -> None:
    member = request.anchor_member(W1_DECLARATION.read_bytes())

    original = curves.materialize(member, obstruction="0.75", clearance_loss="0")
    engine = curves.materialize_net_head(
        member,
        obstruction="0.75",
        clearance_loss="0",
    )

    assert len(engine) == 33
    assert engine[0].head_m == Decimal("0.000000000")
    assert engine[-1].flow_lps == Decimal("0.000000")
    assert all(
        left.head_m < right.head_m
        for left, right in zip(engine, engine[1:], strict=False)
    )
    assert all(
        left.flow_lps >= right.flow_lps
        for left, right in zip(engine, engine[1:], strict=False)
    )
    assert engine[-1].head_m == original[-1].head_m
    assert engine[1].head_m < original[1].head_m
    assert curves.curve_sha256(original) != curves.net_head_curve_sha256(engine)
    assert b"asw-0b5.net-head-pump3-curve.v1" in curves.canonical_net_head_curve_bytes(engine)


def test_each_system_loss_parameter_changes_engine_curve_not_original_curve() -> None:
    member = request.anchor_member(W1_DECLARATION.read_bytes())
    original = curves.materialize(member, obstruction="0", clearance_loss="0")
    baseline = curves.materialize_net_head(member, obstruction="0", clearance_loss="0")

    for identity in (
        "fluid.rho",
        "fluid.mu",
        "fluid.g",
        "system.L",
        "system.D",
        "system.epsilon",
        "system.K_minor",
    ):
        changed = {
            **member,
            "parameters": [
                (
                    {**parameter, "value": _alternate_value(parameter)}
                    if parameter["identity"] == identity
                    else parameter
                )
                for parameter in member["parameters"]
            ],
        }
        changed_original = curves.materialize(changed, obstruction="0", clearance_loss="0")
        changed_engine = curves.materialize_net_head(
            changed,
            obstruction="0",
            clearance_loss="0",
        )

        assert curves.curve_sha256(changed_original) == curves.curve_sha256(original)
        assert curves.net_head_curve_sha256(changed_engine) != curves.net_head_curve_sha256(
            baseline
        )


def _alternate_value(parameter: dict[str, object]) -> str:
    value = Decimal(str(parameter["value"]))
    identity = str(parameter["identity"])
    if identity == "system.D":
        return format(value * Decimal("1.01"), "f")
    return format(value * Decimal("1.10"), "f")
