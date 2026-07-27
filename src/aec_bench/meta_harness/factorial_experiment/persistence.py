# ABOUTME: Persists and reloads content-addressed factorial-experiment specifications and reports.
# ABOUTME: Keeps historical paths, JSON shapes, artifact kinds, and verification-on-load behavior stable.

from __future__ import annotations

from pathlib import Path

from aec_bench.contracts.trial_record import ArtifactReference

from .artifact_io import _pretty_json_bytes, _publish_experiment_bytes
from .contracts import FactorialExperimentReport, FactorialExperimentSpec
from .verification import verify_factorial_experiment_report


def load_factorial_experiment_report(path: Path) -> FactorialExperimentReport:
    """Load a report and revalidate its own identity plus every referenced evidence artifact."""
    source_path = Path(path)
    try:
        report = FactorialExperimentReport.model_validate_json(source_path.read_text(encoding="utf-8"))
    except Exception as error:
        raise ValueError(f"invalid stage-zero report: {source_path}") from error
    if source_path.parent.name != report.content_sha256:
        raise ValueError("stage-zero report path does not match its content identity")
    verify_factorial_experiment_report(report)
    return report


def _write_spec_artifact(spec: FactorialExperimentSpec, *, artifacts_root: Path) -> ArtifactReference:
    payload = {
        "schema_version": "aecbench.meta-harness-stage-zero-preregistration.v1",
        "spec": spec.model_dump(mode="json"),
    }
    encoded = _pretty_json_bytes(payload)
    artifact = _publish_experiment_bytes(
        root=artifacts_root,
        relative_path=(f"stage-zero-specs/{spec.content_sha256}/stage-zero-spec.json"),
        encoded=encoded,
        label="stage-zero spec",
    )
    return ArtifactReference(
        kind="stage-zero-spec",
        path=str(artifact.path),
        sha256=artifact.sha256,
        media_type="application/json",
    )


def _write_report(report: FactorialExperimentReport, *, artifacts_root: Path) -> Path:
    encoded = _pretty_json_bytes(report.model_dump(mode="json"))
    return _publish_experiment_bytes(
        root=artifacts_root,
        relative_path=(f"stage-zero-reports/{report.content_sha256}/stage-zero-report.json"),
        encoded=encoded,
        label="stage-zero report",
    ).path
