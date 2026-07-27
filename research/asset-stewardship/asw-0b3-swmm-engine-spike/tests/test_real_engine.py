# ABOUTME: Executes the pinned real SWMM build twice and validates semantic replay evidence.
# ABOUTME: Deliberately fails without a real build receipt instead of skipping or substituting an engine.

from __future__ import annotations

import os
from pathlib import Path

from asw_b3_swmm.execution import reproduce


def test_pinned_real_engine_replays_with_independent_checks(tmp_path: Path) -> None:
    receipt_value = os.environ.get("ASW_B3_ENGINE_RECEIPT")
    assert receipt_value, "ASW_B3_ENGINE_RECEIPT must name a receipt from a real pinned SWMM build"

    evidence = reproduce(Path(receipt_value), tmp_path / "real-engine-replay")

    assert evidence["status"] == "pass"
    assert evidence["engine"]["version"] == "5.2.4"
    assert evidence["engine"]["commit"] == "7952ca837988b1c32f791812eccc9fd64547e093"
    assert evidence["replay"]["semantic_hashes_match"] is True
    assert evidence["verification"]["all_checks_passed"] is True
