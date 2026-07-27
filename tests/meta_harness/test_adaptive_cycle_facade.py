# ABOUTME: Locks the adaptive-cycle facade to cohesive canonical runtime modules.
# ABOUTME: Characterizes public identity, report bytes, and fail-closed diagnostic order.

from __future__ import annotations

import importlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from aec_bench.contracts.trial_record import ArtifactReference
from aec_bench.meta_harness.adaptive_cycle_runtime.artifacts import (
    write_cycle_report,
)
from aec_bench.meta_harness.adaptive_cycle_runtime.contracts import (
    AdaptiveCycleOutcome,
    AdaptiveCycleReport,
    AdaptiveCycleTerminalReason,
    AdaptiveCycleTerminalStage,
)
from aec_bench.meta_harness.kernel_catalogue import default_kernel_registry
from aec_bench.meta_harness.motif_library import (
    MotifLibrary,
    MotifLibraryArtifact,
    write_motif_library_artifact,
)


def test_adaptive_cycle_facade_reexports_canonical_symbols_by_identity() -> None:
    facade = importlib.import_module("aec_bench.meta_harness.adaptive_cycle")
    canonical = importlib.import_module("aec_bench.meta_harness.adaptive_cycle_runtime")
    contracts = importlib.import_module("aec_bench.meta_harness.adaptive_cycle_runtime.contracts")
    materialization = importlib.import_module("aec_bench.meta_harness.adaptive_cycle_runtime.materialization")
    orchestration = importlib.import_module("aec_bench.meta_harness.adaptive_cycle_runtime.orchestration")
    verification = importlib.import_module("aec_bench.meta_harness.adaptive_cycle_runtime.verification")

    expected = {
        "AdaptiveCycleOutcome": contracts.AdaptiveCycleOutcome,
        "AdaptiveCycleTerminalStage": contracts.AdaptiveCycleTerminalStage,
        "AdaptiveCycleTerminalReason": contracts.AdaptiveCycleTerminalReason,
        "AdaptiveFactorialStageSpec": contracts.AdaptiveFactorialStageSpec,
        "AdaptiveCycleSpec": contracts.AdaptiveCycleSpec,
        "AdaptiveCycleExecutors": contracts.AdaptiveCycleExecutors,
        "AdaptiveCycleReport": contracts.AdaptiveCycleReport,
        "AdaptiveCycleResult": contracts.AdaptiveCycleResult,
        "HarnessMaxTurnsDiagnosisRule": canonical.HarnessMaxTurnsDiagnosisRule,
        "ProgramRetryDiagnosisRule": canonical.ProgramRetryDiagnosisRule,
        "materialize_child_factorial_request": materialization.materialize_child_factorial_request,
        "run_adaptive_cycle": orchestration.run_adaptive_cycle,
        "run_adaptive_cycle_v1_compatibility": orchestration.run_adaptive_cycle_v1_compatibility,
        "load_adaptive_cycle_report": verification.load_adaptive_cycle_report,
        "verify_adaptive_cycle_report": verification.verify_adaptive_cycle_report,
    }
    for name, canonical_object in expected.items():
        assert getattr(facade, name) is canonical_object
        assert getattr(canonical, name) is canonical_object
    assert facade.__all__ == canonical.__all__
    assert set(facade.__all__) == set(expected)


def test_adaptive_cycle_facade_is_stable_under_both_import_orders() -> None:
    programs = (
        """
import aec_bench.meta_harness.adaptive_cycle as facade
import aec_bench.meta_harness.adaptive_cycle_runtime as canonical
assert facade.AdaptiveCycleSpec is canonical.AdaptiveCycleSpec
assert facade.run_adaptive_cycle is canonical.run_adaptive_cycle
assert facade.verify_adaptive_cycle_report is canonical.verify_adaptive_cycle_report
""",
        """
import aec_bench.meta_harness.adaptive_cycle_runtime as canonical
import aec_bench.meta_harness.adaptive_cycle as facade
assert facade.AdaptiveCycleSpec is canonical.AdaptiveCycleSpec
assert facade.run_adaptive_cycle is canonical.run_adaptive_cycle
assert facade.verify_adaptive_cycle_report is canonical.verify_adaptive_cycle_report
""",
    )

    for program in programs:
        subprocess.run([sys.executable, "-c", program], check=True)


def test_cycle_report_writer_preserves_exact_canonical_bytes_and_collision_error(
    tmp_path: Path,
) -> None:
    artifacts = importlib.import_module("aec_bench.meta_harness.adaptive_cycle_runtime.artifacts")
    library = MotifLibrary.create()
    pinned = write_motif_library_artifact(library, artifacts_root=tmp_path / "input-library")
    report = _repair_stop_report(pinned=pinned)
    root = tmp_path / "cycle"

    path = write_cycle_report(report, root=root)

    expected = (json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True) + "\n").encode()
    assert path.read_bytes() == expected
    assert artifacts.write_cycle_report(report, root=root) == path

    path.write_bytes(b"different\n")
    with pytest.raises(
        ValueError,
        match=f"^content-addressed adaptive artifact already contains different bytes: {path}$",
    ):
        artifacts.write_cycle_report(report, root=root)


def test_cycle_report_validation_reports_artifact_kind_before_terminal_shape(
    tmp_path: Path,
) -> None:
    library = MotifLibrary.create()
    pinned = write_motif_library_artifact(library, artifacts_root=tmp_path / "input-library")
    report = _repair_stop_report(pinned=pinned)
    payload = report.model_dump(mode="python", exclude={"content_sha256"})
    payload["source_stage_report"] = pinned.artifact.model_copy(update={"kind": "repair-terminal"})
    payload["child_calibration_report"] = pinned.artifact.model_copy(update={"kind": "stage-zero-report"})

    with pytest.raises(ValidationError) as error:
        AdaptiveCycleReport.model_validate(payload)

    assert error.value.errors()[0]["msg"] == (
        "Value error, adaptive cycle source_stage_report artifact kind must be stage-zero-report"
    )


def test_cycle_report_verification_checks_the_input_archive_first(tmp_path: Path) -> None:
    canonical = importlib.import_module("aec_bench.meta_harness.adaptive_cycle_runtime")
    library = MotifLibrary.create()
    pinned = write_motif_library_artifact(library, artifacts_root=tmp_path / "input-library")
    missing_input = tmp_path / "missing-input-library.json"
    missing_final = tmp_path / "missing-final-library.json"
    report = _repair_stop_report(
        pinned=pinned.model_copy(update={"artifact": pinned.artifact.model_copy(update={"path": str(missing_input)})}),
        final_artifact=pinned.artifact.model_copy(update={"path": str(missing_final)}),
    )

    with pytest.raises(
        ValueError,
        match=f"^adaptive cycle artifact digest mismatch: {missing_input}$",
    ):
        canonical.verify_adaptive_cycle_report(report)


def _repair_stop_report(
    *,
    pinned: MotifLibraryArtifact,
    final_artifact: ArtifactReference | None = None,
) -> AdaptiveCycleReport:
    artifact = pinned.artifact
    return AdaptiveCycleReport(
        outcome=AdaptiveCycleOutcome.STOPPED,
        terminal_stage=AdaptiveCycleTerminalStage.REPAIR,
        terminal_reason=AdaptiveCycleTerminalReason.REPAIR_REJECTED,
        spec_sha256="1" * 64,
        spec_artifact=artifact.model_copy(update={"kind": "adaptive-cycle-spec"}),
        kernel_ref=default_kernel_registry().manifest.ref,
        input_motif_library=pinned,
        source_stage_report=artifact.model_copy(update={"kind": "stage-zero-report"}),
        repair_terminal=artifact.model_copy(update={"kind": "repair-terminal"}),
        motif_library=final_artifact or artifact,
        final_archive_sha256=pinned.archive_sha256,
    )
