# ABOUTME: Runs one real automatic case through independent mass observations.
# ABOUTME: Verifies the fixed solver convergence settings meet unchanged W4 limits.

from __future__ import annotations

import json
import os
from pathlib import Path

from certifier import boundary as certifier_boundary
from certifier import observations
from certifier import physics as certifier_physics
from generator import engine, execution, request
from sensitivity import inputs, mass

B5_ROOT = Path(__file__).parents[2]
W1_DECLARATION = B5_ROOT / "declarations" / "w1-member-authority.json"
W2_CATALOGUE = B5_ROOT / "declarations" / "w2-case-catalogue.json"
W2_W4_REPAIR = (
    B5_ROOT / "declarations" / "w2-w4-engine-mapping-repair.json"
)
SOLVER_CONVERGENCE = (
    B5_ROOT / "declarations" / "solver-convergence-amendment.json"
)


def test_real_clean_automatic_case_meets_amended_mass_limits(
    tmp_path: Path,
) -> None:
    receipt_value = os.environ.get("ASW_B5_ENGINE_RECEIPT")
    assert receipt_value, (
        "ASW_B5_ENGINE_RECEIPT must name the fresh real B5 build receipt"
    )
    receipt_path = Path(receipt_value)
    request_value = request.read_request(
        request.build_anchor_request(
            authority_bytes=W1_DECLARATION.read_bytes(),
            catalogue_bytes=W2_CATALOGUE.read_bytes(),
            case_id="G10_CLEAN_A_BASE",
            engine_identity=engine.request_engine_identity(receipt_path),
            repair_bytes=W2_W4_REPAIR.read_bytes(),
            solver_convergence_bytes=SOLVER_CONVERGENCE.read_bytes(),
        )
    )
    generated = execution.execute_case(
        request_value,
        receipt_path=receipt_path,
        workspace=tmp_path / "G10",
    )
    generated_segment = generated["segments"][0]
    authority = certifier_boundary.read_w1_declaration(
        W1_DECLARATION.read_bytes()
    )
    values = certifier_physics.validate_member(
        request_value["member"],
        authority,
    )
    residuals = observations.segment_observations(
        request=request_value,
        semantic=generated_segment["semantic"],
        values=values,
        segment_id="single",
        carried_depth=None,
    )
    segment = inputs.SegmentEvidence(
        case_id="G10_CLEAN_A_BASE",
        request=request_value,
        role_bytes={},
        role_sha256={},
        segment_id="single",
        semantic=generated_segment["semantic"],
    )

    result = mass._amended_segment(
        segment,
        {"residuals": residuals},
    )

    assert result["first_failure"] == "none", json.dumps(
        result,
        sort_keys=True,
    )
    assert result["step_maximum_ratio"] <= 1.0
    assert result["prefix_maximum_ratio"] <= 1.0
