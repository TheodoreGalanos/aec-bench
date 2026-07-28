# ABOUTME: Specifies the exact W4 C-R08 amendment reader and immutable predecessor binding.
# ABOUTME: Rejects changed authority bytes, failed-result identities, and successor-rule semantics.

from pathlib import Path

import pytest
from sensitivity import amendment

B5_ROOT = Path(__file__).parents[2]
AMENDMENT = B5_ROOT / "declarations" / "w4-c-r08-ceiling-amendment.json"
C_R07_AMENDMENT = (
    B5_ROOT / "declarations" / "w4-c-r07-composition-amendment.json"
)


def test_reads_exact_c_r08_amendment_and_bound_failed_generation() -> None:
    value = amendment.read_amendment(AMENDMENT.read_bytes())

    assert value["authority"]["repair_schema_id"] == (
        "asw-0b5.w4-c-r08-ceiling-amendment.v1"
    )
    assert value["failed_execution"]["generation_id"] == (
        "255e5b5cce2b4361bf37857ffbb386ef233bca47e9051b8f25e1689077edff06"
    )
    assert value["rules"]["C-R08"]["dynamic_rule_ceiling"] == (
        "B_dynamic_Q<=C08"
    )
    assert value["rules"]["C-R08"]["numerical_rule_ceiling"] == (
        "T08_numerical<=C08"
    )
    assert value["boundaries"]["result_edit_in_place_allowed"] is False


def test_rejects_any_changed_amendment_byte() -> None:
    raw = AMENDMENT.read_bytes()
    changed = raw.replace(
        b'"fresh_complete_affected_run_required": true',
        b'"fresh_complete_affected_run_required": false',
    )

    with pytest.raises(
        amendment.AmendmentBoundaryError,
        match="amendment bytes differ",
    ):
        amendment.read_amendment(changed)


def test_reads_exact_c_r07_amendment_and_paired_closure_rule() -> None:
    value = amendment.read_c_r07_amendment(C_R07_AMENDMENT.read_bytes())

    assert value["authority"]["repair_schema_id"] == (
        "asw-0b5.w4-c-r07-composition-amendment.v1"
    )
    assert value["authority"]["c_r08_amendment_sha256"] == (
        amendment.C_R08_AMENDMENT_SHA256
    )
    assert value["rules"]["C-R07"]["tolerance_rule"] == (
        "T07=outward_sum(B32(H_discharge),B32(H_wet-well),"
        "B_curve_H(32,o,c),B_render_head,B_system_render,B64(H_system))"
    )
    assert value["boundaries"]["v1_generation_reload_required"] is True


def test_rejects_any_changed_c_r07_amendment_byte() -> None:
    raw = C_R07_AMENDMENT.read_bytes()
    changed = raw.replace(
        b'"base-curve-segments=32"',
        b'"base-curve-segments=64"',
    )

    with pytest.raises(
        amendment.AmendmentBoundaryError,
        match="C-R07 amendment bytes differ",
    ):
        amendment.read_c_r07_amendment(changed)
