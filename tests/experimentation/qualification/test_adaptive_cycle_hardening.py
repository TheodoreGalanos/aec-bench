# ABOUTME: Exercises pinned motif libraries and current adaptive-cycle terminal reports.
# ABOUTME: Proves corrupted archives and invalid evidence prefixes fail before reuse claims.

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from aec_bench.experimentation.governance.motifs import (
    MotifLibrary,
    load_pinned_motif_library,
    write_motif_library_artifact,
)
from aec_bench.experimentation.qualification.adaptive_cycle_runtime import (
    AdaptiveCycleOutcome,
    AdaptiveCycleReport,
    AdaptiveCycleTerminalReason,
    AdaptiveCycleTerminalStage,
)
from aec_bench.harness.kernel_catalogue import default_kernel_registry


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
        "source_stage_report": artifact.model_copy(update={"kind": "harness-program-study-report"}),
        "repair_terminal": artifact.model_copy(update={"kind": "repair-terminal"}),
        "motif_library": artifact,
        "final_archive_sha256": library.archive_sha256,
    }

    report = AdaptiveCycleReport.model_validate(payload)

    assert report.child_calibration_report is None
    assert report.final_status is None
    invalid = report.model_dump(mode="python", exclude={"content_sha256"})
    invalid["child_calibration_report"] = artifact.model_copy(update={"kind": "harness-program-study-report"})
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
