# ABOUTME: Exercises strict Phase 6/7 boundaries for pinned motif libraries and adaptive-cycle terminal reports.
# ABOUTME: Proves corrupted archives and invalid terminal artifact shapes fail before they can support reuse claims.

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from aec_bench.meta_harness.adaptive_cycle import (
    AdaptiveCycleOutcome,
    AdaptiveCycleReport,
    AdaptiveCycleTerminalReason,
    AdaptiveCycleTerminalStage,
)
from aec_bench.meta_harness.kernel_catalogue import default_kernel_registry
from aec_bench.meta_harness.motif_library import (
    MotifLibrary,
    load_pinned_motif_library,
    write_motif_library_artifact,
)


def test_empty_motif_library_is_explicitly_pinned_and_tamper_evident(tmp_path: Path) -> None:
    library = MotifLibrary.create()

    pinned = write_motif_library_artifact(library, artifacts_root=tmp_path)

    assert pinned.archive_sha256 == library.archive_sha256
    assert load_pinned_motif_library(pinned) == library
    Path(pinned.artifact.path).write_text("{}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="motif library artifact digest mismatch"):
        load_pinned_motif_library(pinned)


def test_repair_stop_report_requires_the_exact_prefix_and_unchanged_archive(tmp_path: Path) -> None:
    library = MotifLibrary.create()
    pinned = write_motif_library_artifact(library, artifacts_root=tmp_path / "libraries")
    artifact = pinned.artifact
    payload = {
        "outcome": AdaptiveCycleOutcome.STOPPED,
        "terminal_stage": AdaptiveCycleTerminalStage.REPAIR,
        "terminal_reason": AdaptiveCycleTerminalReason.REPAIR_REJECTED,
        "spec_sha256": "1" * 64,
        "spec_artifact": artifact.model_copy(update={"kind": "adaptive-cycle-spec"}),
        "kernel_ref": default_kernel_registry().manifest.ref,
        "input_motif_library": pinned,
        "source_stage_report": artifact.model_copy(update={"kind": "stage-zero-report"}),
        "repair_terminal": artifact.model_copy(update={"kind": "repair-terminal"}),
        "motif_library": artifact,
        "final_archive_sha256": library.archive_sha256,
    }

    report = AdaptiveCycleReport.model_validate(payload)

    assert report.child_calibration_report is None
    assert report.final_status is None
    invalid = report.model_dump(mode="python", exclude={"content_sha256"})
    invalid["child_calibration_report"] = artifact.model_copy(update={"kind": "stage-zero-report"})
    with pytest.raises(ValidationError, match="artifact shape"):
        AdaptiveCycleReport.model_validate(invalid)

    changed_archive = report.model_dump(mode="python", exclude={"content_sha256"})
    changed_archive["final_archive_sha256"] = "2" * 64
    with pytest.raises(ValidationError, match="input archive"):
        AdaptiveCycleReport.model_validate(changed_archive)

    wrong_kind = report.model_dump(mode="python", exclude={"content_sha256"})
    wrong_kind["source_stage_report"] = artifact.model_copy(update={"kind": "repair-terminal"})
    with pytest.raises(ValidationError, match="artifact kind"):
        AdaptiveCycleReport.model_validate(wrong_kind)


def test_transfer_terminal_report_requires_every_downstream_artifact(tmp_path: Path) -> None:
    library = MotifLibrary.create()
    pinned = write_motif_library_artifact(library, artifacts_root=tmp_path / "libraries")
    artifact = pinned.artifact
    payload = {
        "outcome": AdaptiveCycleOutcome.COMPLETED,
        "terminal_stage": AdaptiveCycleTerminalStage.TRANSFER_PROMOTION,
        "terminal_reason": AdaptiveCycleTerminalReason.TRANSFER_VALIDATED,
        "spec_sha256": "1" * 64,
        "spec_artifact": artifact.model_copy(update={"kind": "adaptive-cycle-spec"}),
        "kernel_ref": default_kernel_registry().manifest.ref,
        "input_motif_library": pinned,
        "source_stage_report": artifact.model_copy(update={"kind": "stage-zero-report"}),
        "repair_terminal": artifact.model_copy(update={"kind": "repair-terminal"}),
        "repaired_candidate": artifact.model_copy(update={"kind": "repair-candidate"}),
        "child_calibration_report": artifact.model_copy(update={"kind": "stage-zero-report"}),
        "motif_learning_report": artifact.model_copy(update={"kind": "motif-learning-report"}),
        "learning_motif_library": artifact,
        "transfer_evaluation_report": artifact.model_copy(update={"kind": "motif-transfer-evaluation"}),
        "transfer_promotion_report": artifact.model_copy(update={"kind": "motif-transfer-promotion-report"}),
        "motif_library": artifact,
        "learned_motif_sha256": "2" * 64,
        "learning_archive_sha256": library.archive_sha256,
        "final_motif_sha256": "3" * 64,
        "final_archive_sha256": library.archive_sha256,
        "final_status": "transfer_validated",
    }
    payload.pop("transfer_evaluation_report")

    with pytest.raises(ValidationError, match="artifact shape"):
        AdaptiveCycleReport.model_validate(payload)
