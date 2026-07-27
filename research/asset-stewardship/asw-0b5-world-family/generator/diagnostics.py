# ABOUTME: Parses the pinned SWMM report into the exact normalized W1 diagnostic facts.
# ABOUTME: Rejects every warning, error, missing completion marker, or non-converging execution.

from __future__ import annotations

import re
from typing import Any

ERROR_PATTERN = re.compile(rb"\bERROR\s+\d+\b", re.IGNORECASE)
WARNING_PATTERN = re.compile(rb"\bWARNING\s+\d+\b", re.IGNORECASE)
CONTINUITY_PATTERN = re.compile(
    rb"Continuity Error\s*\(%\)\s*\.+\s*([+-]?\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
NONCONVERGING_PATTERN = re.compile(
    rb"% of Steps Not Converging\s*:\s*(\d+(?:\.\d+)?)",
    re.IGNORECASE,
)


class DiagnosticsError(RuntimeError):
    """Raised when a pinned SWMM report fails the W1 diagnostic profile."""


def _identifiers(pattern: re.Pattern[bytes], raw: bytes) -> list[str]:
    return sorted({match.decode("ascii").upper() for match in pattern.findall(raw)})


def parse_report_bytes(raw: bytes) -> dict[str, Any]:
    """Return fail-closed, path-free diagnostic facts from exact report bytes."""
    errors = _identifiers(ERROR_PATTERN, raw)
    warnings = _identifiers(WARNING_PATTERN, raw)
    if errors or warnings:
        identifiers = ", ".join([*errors, *warnings])
        raise DiagnosticsError(f"SWMM report contains {identifiers}")
    continuity = CONTINUITY_PATTERN.findall(raw)
    nonconverging = NONCONVERGING_PATTERN.findall(raw)
    completion = b"Analysis begun on:" in raw and b"Analysis ended on:" in raw
    all_steps = b"Convergence obtained at all time steps." in raw
    if len(continuity) != 1:
        raise DiagnosticsError("flow-routing continuity diagnostic is absent or ambiguous")
    if len(nonconverging) != 1:
        raise DiagnosticsError("non-converging-step diagnostic is absent or ambiguous")
    if not completion:
        raise DiagnosticsError("analysis completion marker is absent")
    if not all_steps:
        raise DiagnosticsError("all-steps convergence marker is absent")
    nonconverging_text = nonconverging[0].decode("ascii")
    if nonconverging_text != "0.00":
        raise DiagnosticsError(
            f"steps not converging must be exact 0.00, received {nonconverging_text}"
        )
    return {
        "completion_marker": completion,
        "convergence_at_all_steps": all_steps,
        "errors": errors,
        "flow_routing_continuity_error_percent": continuity[0].decode("ascii"),
        "steps_not_converging_percent": nonconverging_text,
        "warnings": warnings,
    }
