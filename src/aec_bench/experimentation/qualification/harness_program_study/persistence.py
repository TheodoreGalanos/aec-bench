# ABOUTME: Persists and reloads content-addressed harness-program-study specifications and reports.
# ABOUTME: Keeps paths, JSON shapes, artifact kinds, and verification-on-load behaviour consistent.

from __future__ import annotations

from pathlib import Path

from aec_bench.contracts.trial_record import ArtifactReference

from .artifact_io import _pretty_json_bytes, _publish_experiment_bytes
from .contracts import HarnessProgramStudyReport, HarnessProgramStudySpec
from .verification import verify_harness_program_study_report


def load_harness_program_study_report(path: Path) -> HarnessProgramStudyReport:
    """Load a report and revalidate its own identity plus every referenced evidence artifact."""
    source_path = Path(path)
    try:
        report = HarnessProgramStudyReport.model_validate_json(source_path.read_text(encoding="utf-8"))
    except Exception as error:
        raise ValueError(f"invalid harness-program-study report: {source_path}") from error
    if source_path.parent.name != report.content_sha256:
        raise ValueError("harness-program-study report path does not match its content identity")
    verify_harness_program_study_report(report)
    return report


def _write_spec_artifact(spec: HarnessProgramStudySpec, *, artifacts_root: Path) -> ArtifactReference:
    payload = {
        "schema_version": "aecbench.harness-program-study-preregistration.v1",
        "spec": spec.model_dump(mode="json"),
    }
    encoded = _pretty_json_bytes(payload)
    artifact = _publish_experiment_bytes(
        root=artifacts_root,
        relative_path=(f"harness-program-study-specs/{spec.content_sha256}/harness-program-study-spec.json"),
        encoded=encoded,
        label="harness-program-study spec",
    )
    return ArtifactReference(
        kind="harness-program-study-spec",
        path=str(artifact.path),
        sha256=artifact.sha256,
        media_type="application/json",
    )


def _write_report(report: HarnessProgramStudyReport, *, artifacts_root: Path) -> Path:
    encoded = _pretty_json_bytes(report.model_dump(mode="json"))
    return _publish_experiment_bytes(
        root=artifacts_root,
        relative_path=(f"harness-program-study-reports/{report.content_sha256}/harness-program-study-report.json"),
        encoded=encoded,
        label="harness-program-study report",
    ).path
