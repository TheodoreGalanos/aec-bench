# ABOUTME: Runs the complete real-engine reference certification and package issuance workflow.
# ABOUTME: Verifies the issued package, compact record, and connected receipt count at the outer boundary.

import json
import os
from pathlib import Path

from promotion import package_checker
from run_reference_certification import (
    execute_reference_certification,
)


def test_complete_real_reference_certification_issues_checked_package(
    tmp_path: Path,
) -> None:
    receipt_value = os.environ.get("ASW_B5_ENGINE_RECEIPT")
    assert receipt_value, (
        "ASW_B5_ENGINE_RECEIPT must name the real B5 engine receipt"
    )
    output_value = os.environ.get("ASW_B5_CERTIFICATION_OUTPUT")
    output_root = (
        Path(output_value)
        if output_value is not None
        else tmp_path / "reference-certification"
    )

    summary = execute_reference_certification(
        engine_receipt=Path(receipt_value),
        output_root=output_root,
    )

    package_root = output_root / "certified-reference-package"
    compact_root = output_root / "certification-record"
    conformance = package_checker.check_package(package_root)
    stored_summary = json.loads(
        (compact_root / "certification-summary.json").read_bytes()
    )
    receipt_index = json.loads(
        (compact_root / "receipt-index.json").read_bytes()
    )

    assert stored_summary == summary
    assert summary["promotion_terminal_state"] == (
        "promotion-v3-issued"
    )
    assert summary["v3"] == "issued"
    assert summary["v4"] == "unclaimed"
    assert summary["receipt_count"] == 13
    assert len(receipt_index["receipts"]) == 13
    assert conformance["terminal_state"] == (
        "package-conformance-pass"
    )
    assert conformance["package_content_id"] == (
        summary["package_content_id"]
    )
    assert {path.name for path in package_root.iterdir()} == {
        "physical-member.json",
        "physical-reference-checks.json",
        "promotion-manifest.json",
        "public-profile.json",
    }
