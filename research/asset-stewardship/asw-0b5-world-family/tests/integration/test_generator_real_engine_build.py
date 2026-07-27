# ABOUTME: Verifies a fresh B5 build receipt against actual pinned SWMM artifacts and upstream tests.
# ABOUTME: Fails instead of skipping when the real engine receipt is absent, stale, patched differently, or incomplete.

from __future__ import annotations

import os
from pathlib import Path

from generator import engine


def test_real_pinned_engine_build_receipt_and_artifacts() -> None:
    receipt_value = os.environ.get("ASW_B5_ENGINE_RECEIPT")
    assert receipt_value, "ASW_B5_ENGINE_RECEIPT must name a fresh real B5 SWMM build receipt"

    verified = engine.verify_build_receipt(Path(receipt_value))

    assert verified["schema_id"] == "asw-0b5.engine-build-receipt.v1"
    assert verified["source"]["repository"] == engine.SWMM_REPOSITORY
    assert verified["source"]["commit"] == engine.SWMM_COMMIT
    assert verified["source"]["version"] == engine.SWMM_VERSION
    assert verified["patch"]["sha256"] == engine.SWMM_PATCH_SHA256
    assert verified["build"]["build_type"] == "Release"
    assert verified["build"]["parallelism"] == 1
    assert verified["upstream_tests"]["status"] == "pass"
    assert verified["promotable"] is False

