# ABOUTME: Reads the exact control-edge trajectory amendment and its fixed boundary.
# ABOUTME: Exposes no candidate parsing, trajectory calculation, or promotion behavior.

from __future__ import annotations

import hashlib
import json
from typing import Any, cast

AMENDMENT_SHA256 = (
    "161ae844049b6f7956b122827c693b59b68f99adc574af8f54454270f66ccc2a"
)


class ControlEdgeTrajectoryError(ValueError):
    """Raised when the approved control-edge authority differs."""


def read_amendment(raw: bytes) -> dict[str, Any]:
    """Return the exact approved control-edge trajectory amendment."""
    if hashlib.sha256(raw).hexdigest() != AMENDMENT_SHA256:
        raise ControlEdgeTrajectoryError(
            "control-edge trajectory amendment bytes differ"
        )
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ControlEdgeTrajectoryError(
            f"control-edge trajectory amendment JSON differs: {error}"
        ) from error
    if not isinstance(value, dict) or set(value) != {
        "authority",
        "boundaries",
        "preserved",
        "rules",
        "status",
    }:
        raise ControlEdgeTrajectoryError(
            "control-edge trajectory amendment shape differs"
        )
    document = cast(dict[str, Any], value)
    authority = document["authority"]
    boundaries = document["boundaries"]
    rules = document["rules"]
    if (
        document["status"] != "approved-before-fresh-successor-run"
        or authority.get("repair_schema_id")
        != "asw-0b5.control-edge-trajectory-amendment.v1"
        or authority.get("engine_commit")
        != "7952ca837988b1c32f791812eccc9fd64547e093"
        or authority.get("c_r02_amendment_sha256")
        != "d6ada0600f06d5aedd3298882f4e1fdab815eeddc15edc06eb3bc222d60979c5"
        or authority.get("solver_convergence_amendment_sha256")
        != "583efcc11501bbe4a07dce8de5c50ae2c6c8dd72d9af76a29eff7ebc47f39859"
        or boundaries
        != {
            "candidate_depth_or_flow_allowed_as_reference_input": False,
            "candidate_edge_timestamps_allowed_after_c_r12_pass": True,
            "changes_physical_model": False,
            "changes_tolerance_or_hard_ceiling": False,
            "edge_fitting_shifting_or_best_fit_allowed": False,
            "fresh_affected_run_required": True,
            "package_before_family_pass_allowed": False,
            "production_import_allowed": False,
        }
        or rules.get("C-R10", {}).get("allowed_candidate_input")
        != "validated-pump-setting-label-and-timestamp-only"
        or rules.get("C-R10", {}).get("corrected_residual_rule")
        != "r_depth,corrected=r_depth,raw-E_edge,h-E_route,h"
        or rules.get("C-R11", {}).get("allowed_candidate_input")
        != "validated-pump-setting-label-and-timestamp-only"
        or rules.get("C-R11", {}).get("corrected_residual_rule")
        != "r_flow,corrected=r_flow,raw-E_edge,Q-E_route,Q"
        or rules.get("validation_order")
        != [
            "verify-exact-amendment-bytes",
            "verify-settings-v3",
            "verify-W3-exact-and-qualitative-pass",
            "verify-C-R12-before-reading-edge-labels-or-times",
            "freeze-validated-setting-trace",
            "recompute-independent-trajectory",
            "apply-signed-edge-and-routing-corrections",
            "apply-unchanged-budgets-and-ceilings",
        ]
    ):
        raise ControlEdgeTrajectoryError(
            "control-edge trajectory amendment authority differs"
        )
    return document
