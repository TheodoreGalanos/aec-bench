# ABOUTME: Reconstructs the complete W2 case catalogue independently from frozen protocol rules and W1 values.
# ABOUTME: Rejects undeclared case, state, transition, exposure, schedule, or duty variation without generator input.

from __future__ import annotations

import hashlib
from decimal import Decimal
from typing import Any

from certifier import boundary

CASE_DOMAIN = b"asw-0b4.case.v1\0"
STATE_DOMAIN = b"asw-0b4.pump-state.v1\0"
ASSIGNMENT_DOMAIN = b"asw-0b4.duty-assignment.v1\0"

FORCED_STATES = {
    "G12_CLEAN_ASSESS": ("0", "0"),
    "G20_OBSTRUCTION_HALF": ("0.50", "0"),
    "G21_OBSTRUCTION_TRIGGER": ("0.75", "0"),
    "G22_OBSTRUCTION_UPPER": ("1", "0"),
    "G30_CLEARANCE_HALF": ("0", "0.50"),
    "G31_CLEARANCE_UPPER": ("0", "1"),
    "G40_COMBINED_HALF": ("0.50", "0.50"),
    "G41_COMBINED_UPPER": ("1", "1"),
    "G50_CLEAR_A_PRE": ("0.65", "0.10"),
    "G51_CLEAR_A_POST": ("0.0975", "0.10"),
    "G52_CLEAR_B_PRE": ("0.25", "0.742300"),
    "G53_CLEAR_B_POST": ("0.0375", "0.742300"),
    "G60_REPAIR_PRE": ("0.50", "0.50"),
    "G61_REPAIR_POST": ("0.50", "0.05"),
}

INTERVENTIONS = {
    "G51_CLEAR_A_POST": (
        {"clearance-loss": "0.10", "obstruction": "0.65"},
        {"clearance-loss": "0.10", "obstruction": "0.0975"},
        "obstruction-clearing",
        "asw-0b4.rule.obstruction-clearing.v1",
    ),
    "G53_CLEAR_B_POST": (
        {"clearance-loss": "0.742300", "obstruction": "0.25"},
        {"clearance-loss": "0.742300", "obstruction": "0.0375"},
        "obstruction-clearing",
        "asw-0b4.rule.obstruction-clearing.v1",
    ),
    "G61_REPAIR_POST": (
        {"clearance-loss": "0.50", "obstruction": "0.50"},
        {"clearance-loss": "0.05", "obstruction": "0.50"},
        "clearance-repair",
        "asw-0b4.rule.clearance-repair.v1",
    ),
}


class CaseError(ValueError):
    """Raised when a request case differs from the independently frozen catalogue."""


def _content_id(domain: bytes, value: object) -> str:
    return hashlib.sha256(domain + boundary.canonical_json_bytes(value)).hexdigest()


def _with_case_id(value: dict[str, Any]) -> dict[str, Any]:
    value["case_content_id"] = _content_id(
        CASE_DOMAIN,
        {key: child for key, child in value.items() if key != "case_content_id"},
    )
    return value


def _state_id(state: dict[str, str]) -> str:
    return _content_id(STATE_DOMAIN, state)


def _assignment_id(assignment: str) -> str:
    return hashlib.sha256(ASSIGNMENT_DOMAIN + assignment.encode("ascii")).hexdigest()


def _clean_state() -> dict[str, str]:
    return {"clearance-loss": "0", "obstruction": "0"}


def _exposure(runtime_s: int = 0, starts: int = 0) -> dict[str, int]:
    return {
        "calendar_s": runtime_s,
        "completed_starts": starts,
        "runtime_s": runtime_s,
    }


def _decimal_text(value: Decimal) -> str:
    rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return "0" if rendered in {"", "-0"} else rendered


def _progressed_state(
    values: dict[str, Decimal],
    runtime_s: int,
    starts: int,
) -> dict[str, str]:
    obstruction = min(
        Decimal(1),
        values["mechanism.r_o_runtime"] * runtime_s
        + values["mechanism.r_o_start"] * starts,
    )
    clearance = min(
        Decimal(1),
        values["mechanism.r_c_runtime"] * runtime_s,
    )
    return {
        "clearance-loss": _decimal_text(clearance),
        "obstruction": _decimal_text(obstruction),
    }


def _base_case(case_id: str) -> dict[str, Any]:
    return {
        "case_content_id": "",
        "case_id": case_id,
        "checkpoints": [],
        "control_mode": "forced-on",
        "exposure_state": {
            "pump-a": _exposure(),
            "pump-b": _exposure(),
        },
        "family": "hydraulic-diagnostic",
        "history_retained": True,
        "horizon_s": 120,
        "inflow_stimulus": "constant-assessment",
        "initial_depth_source": "well.h_start",
        "mechanism_state": {
            "pump-a": _clean_state(),
            "pump-b": _clean_state(),
        },
        "non_promotable_boundary": False,
        "physical_transitions": [],
        "segments": [],
        "selected_pump": "pump-a",
    }


def expected_case(
    case_id: str,
    values: dict[str, Decimal],
) -> dict[str, Any]:
    """Return the independently reconstructed exact request case."""
    if case_id not in boundary.W2_CASES:
        raise CaseError(f"unknown case {case_id!r}")
    case = _base_case(case_id)
    if case_id == "G00_ZERO_STATIC":
        case.update(
            {
                "control_mode": "forced-off",
                "family": "static-boundary",
                "horizon_s": 3600,
                "inflow_stimulus": "zero",
                "non_promotable_boundary": True,
                "selected_pump": "none",
            }
        )
    elif case_id in {"G10_CLEAN_A_BASE", "G11_CLEAN_B_BASE"}:
        case.update(
            {
                "control_mode": "automatic",
                "family": "automatic-base",
                "horizon_s": 28800,
                "inflow_stimulus": "base-pattern",
                "initial_depth_source": "well.h_stop",
                "selected_pump": (
                    "pump-a" if case_id == "G10_CLEAN_A_BASE" else "pump-b"
                ),
            }
        )
    elif case_id in FORCED_STATES:
        obstruction, clearance = FORCED_STATES[case_id]
        case["mechanism_state"]["pump-a"] = {
            "clearance-loss": clearance,
            "obstruction": obstruction,
        }
        if case_id in INTERVENTIONS:
            before, after, effect, rule = INTERVENTIONS[case_id]
            case["physical_transitions"] = [
                {
                    "after_state_content_id": _state_id(after),
                    "before_state_content_id": _state_id(before),
                    "effect_kind": effect,
                    "effective_second": 0,
                    "rule_identity": rule,
                    "target_pump": "pump-a",
                }
            ]
    elif case_id == "G70_TRANSFER":
        case["mechanism_state"]["pump-a"]["obstruction"] = "0.75"
        case.update(
            {
                "control_mode": "transfer",
                "family": "transfer-sequence",
                "physical_transitions": [
                    {
                        "after_state_content_id": _assignment_id("pump-b"),
                        "before_state_content_id": _assignment_id("pump-a"),
                        "effect_kind": "duty-transfer",
                        "effective_second": 60,
                        "rule_identity": "asw-0b4.rule.transfer.v1",
                        "target_pump": "pump-a-to-pump-b",
                    }
                ],
                "segments": [
                    {
                        "horizon_s": 60,
                        "local_end_s": 60,
                        "local_start_s": 1,
                        "selected_pump": "pump-a",
                    },
                    {
                        "horizon_s": 60,
                        "local_end_s": 60,
                        "local_start_s": 1,
                        "selected_pump": "pump-b",
                    },
                ],
                "selected_pump": "pump-a-to-pump-b",
            }
        )
    elif case_id == "G80_NO_MAINTENANCE":
        exposures = (
            (0, 0),
            (3_600_000, 500),
            (7_200_000, 1_000),
            (10_800_000, 2_000),
        )
        case.update(
            {
                "checkpoints": [
                    {
                        "checkpoint_index": index,
                        "exposure": _exposure(runtime_s, starts),
                        "mechanism_state": _progressed_state(
                            values,
                            runtime_s,
                            starts,
                        ),
                    }
                    for index, (runtime_s, starts) in enumerate(exposures)
                ],
                "family": "progression-checkpoints",
            }
        )
    else:
        raise CaseError(f"case reconstruction absent for {case_id!r}")
    return _with_case_id(case)


def validate_case(
    case: dict[str, Any],
    values: dict[str, Decimal],
) -> dict[str, Any]:
    """Require exact equality with the independently reconstructed case."""
    case_id = case.get("case_id")
    if not isinstance(case_id, str):
        raise CaseError("case identifier is absent")
    expected = expected_case(case_id, values)
    if case != expected:
        raise CaseError(f"case {case_id} differs from the frozen catalogue")
    return case
