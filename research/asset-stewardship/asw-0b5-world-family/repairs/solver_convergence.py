# ABOUTME: Reads the exact solver convergence amendment and exposes its fixed options.
# ABOUTME: Keeps numerical solver controls separate from physical and acceptance rules.

from __future__ import annotations

import hashlib
import json
from typing import Any, cast

AMENDMENT_SHA256 = (
    "583efcc11501bbe4a07dce8de5c50ae2c6c8dd72d9af76a29eff7ebc47f39859"
)
ENGINE_SETTINGS_ID = "asw-0b5.swmm-settings.v3"
HEAD_TOLERANCE_M = "0.0000001"
MAX_TRIALS = 50


class SolverConvergenceError(ValueError):
    """Raised when the solver convergence authority differs."""


def read_amendment(raw: bytes) -> dict[str, Any]:
    """Return the exact approved solver convergence amendment."""
    if hashlib.sha256(raw).hexdigest() != AMENDMENT_SHA256:
        raise SolverConvergenceError(
            "solver convergence amendment bytes differ"
        )
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SolverConvergenceError(
            f"solver convergence amendment JSON differs: {error}"
        ) from error
    if not isinstance(value, dict) or set(value) != {
        "authority",
        "boundaries",
        "derivation",
        "engine_options",
        "failed_execution",
        "source_evidence",
        "status",
    }:
        raise SolverConvergenceError(
            "solver convergence amendment shape differs"
        )
    document = cast(dict[str, Any], value)
    if (
        document["status"] != "approved-before-fresh-certification"
        or document["authority"].get("amendment_schema_id")
        != "asw-0b5.solver-convergence-amendment.v1"
        or document["authority"].get("engine_commit")
        != "7952ca837988b1c32f791812eccc9fd64547e093"
        or document["authority"].get("engine_settings_id")
        != ENGINE_SETTINGS_ID
        or document["authority"].get("engine_settings_predecessor_id")
        != "asw-0b5.swmm-settings.v2"
        or document["boundaries"].get(
            "candidate_values_used_to_select_acceptance_limits"
        )
        is not False
        or document["boundaries"].get(
            "adds_source_derived_method_bound"
        )
        is not True
        or document["boundaries"].get(
            "changes_preregistered_hard_ceilings"
        )
        is not False
        or document["boundaries"].get("changes_physical_model")
        is not False
        or document["derivation"].get(
            "per_interval_storage_method_bound_rule"
        )
        != "wet-well-area-times-HEAD_TOLERANCE"
        or document["derivation"].get(
            "cumulative_method_bound_rule"
        )
        != (
            "sum-per-interval-bounds-because-iteration-remainders-"
            "can-share-sign"
        )
        or document["engine_options"]
        != {
            "HEAD_TOLERANCE": HEAD_TOLERANCE_M,
            "MAX_TRIALS": MAX_TRIALS,
        }
    ):
        raise SolverConvergenceError(
            "solver convergence amendment authority differs"
        )
    return document
