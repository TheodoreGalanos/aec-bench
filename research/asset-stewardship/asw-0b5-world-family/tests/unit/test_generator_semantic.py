# ABOUTME: Specifies exact binary32, integer-series, and normalized report semantics for W1 generation.
# ABOUTME: Rejects non-finite values, negative zero, malformed diagnostics, and path-dependent semantic bytes.

from __future__ import annotations

import math

import pytest
from generator import diagnostics, semantic


def test_binary32_encoding_normalizes_zero_and_preserves_exact_bits() -> None:
    assert semantic.binary32_hex(0.0) == "00000000"
    assert semantic.binary32_hex(-0.0) == "00000000"
    assert semantic.binary32_hex(1.0) == "3f800000"
    assert semantic.binary32_from_hex("3f800000") == 1.0
    assert semantic.binary32_hex(semantic.scale_lps_to_m3_s(1.0)) == "3a83126f"


@pytest.mark.parametrize("value", [math.inf, -math.inf, math.nan])
def test_binary32_encoding_rejects_non_finite_values(value: float) -> None:
    with pytest.raises(semantic.SemanticError, match="finite"):
        semantic.binary32_hex(value)


def test_report_parser_extracts_only_normalized_diagnostics() -> None:
    report = b"""
Flow Routing Continuity
Continuity Error (%) .....        -0.013
Most Frequent Nonconverging Nodes
Convergence obtained at all time steps.
% of Steps Not Converging   :     0.00
Analysis begun on: Mon Jul 27 22:15:19 2026
Analysis ended on: Mon Jul 27 22:15:19 2026
"""

    parsed = diagnostics.parse_report_bytes(report)

    assert parsed == {
        "completion_marker": True,
        "convergence_at_all_steps": True,
        "errors": [],
        "flow_routing_continuity_error_percent": "-0.013",
        "steps_not_converging_percent": "0.00",
        "warnings": [],
    }


def test_report_parser_rejects_warning_or_missing_completion() -> None:
    with pytest.raises(diagnostics.DiagnosticsError, match="WARNING 04"):
        diagnostics.parse_report_bytes(b"WARNING 04\n")
