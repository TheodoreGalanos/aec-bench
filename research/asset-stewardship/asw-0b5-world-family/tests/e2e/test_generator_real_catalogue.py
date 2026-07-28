# ABOUTME: Runs every canonical W2 case twice through fresh real-engine workspaces.
# ABOUTME: Requires exact 23-segment inventory, ordering, carry, raw replay, setting replay, and semantic replay.

from __future__ import annotations

import os
from pathlib import Path

from generator import execution, request

B5_ROOT = Path(__file__).parents[2]
W1_DECLARATION = B5_ROOT / "declarations" / "w1-member-authority.json"
W2_CATALOGUE = B5_ROOT / "declarations" / "w2-case-catalogue.json"
W2_W4_REPAIR = B5_ROOT / "declarations" / "w2-w4-engine-mapping-repair.json"
SOLVER_CONVERGENCE = (
    B5_ROOT / "declarations" / "solver-convergence-amendment.json"
)


def test_complete_real_catalogue_replays_exactly(tmp_path: Path) -> None:
    receipt_value = os.environ.get("ASW_B5_ENGINE_RECEIPT")
    assert receipt_value, "ASW_B5_ENGINE_RECEIPT must name the fresh real B5 build receipt"

    result = execution.execute_catalogue(
        authority_bytes=W1_DECLARATION.read_bytes(),
        catalogue_bytes=W2_CATALOGUE.read_bytes(),
        receipt_path=Path(receipt_value),
        repair_bytes=W2_W4_REPAIR.read_bytes(),
        solver_convergence_bytes=SOLVER_CONVERGENCE.read_bytes(),
        workspace=tmp_path / "catalogue",
    )

    assert result["case_ids"] == list(request.CASE_IDS)
    assert result["segment_count_per_replay"] == 23
    assert result["engine_execution_count"] == 46
    assert result["replay"]["rendered_inputs_equal"] is True
    assert result["replay"]["raw_binary_outputs_equal"] is True
    assert result["replay"]["setting_traces_equal"] is True
    assert result["replay"]["semantic_outputs_equal"] is True
    assert result["replay"]["normalized_diagnostics_equal"] is True
    assert result["replay"]["run_set_hashes_equal"] is True
    transfer = result["replays"][0]["cases"]["G70_TRANSFER"]
    assert [segment["segment_id"] for segment in transfer["segments"]] == [
        "segment-a",
        "segment-b",
    ]
    assert transfer["carry"]["source"] == "segment-a:wet_well_depth_m:last"
    assert transfer["carry"]["representation"] == "ieee754-binary32-be-hex"
