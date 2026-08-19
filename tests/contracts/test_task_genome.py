# ABOUTME: Tests for task genome sidecar contract models.
# ABOUTME: Verifies provenance, pressure points, and manifest validation behavior.

import pytest
from pydantic import ValidationError

from aec_bench.contracts.artifacts import ArtifactRef
from aec_bench.contracts.task_genome import (
    DomainFrame,
    ExtractionSummary,
    InputBundle,
    OutputContract,
    PressurePoint,
    Scenario,
    SourceSpan,
    TaskGenomeManifest,
    TaskGenomeReview,
    VerifierContract,
)
from aec_bench.contracts.task_snapshot import ArtifactTaskSnapshotRef as TaskSnapshotRef


def build_manifest(**overrides: object) -> TaskGenomeManifest:
    payload = {
        "task_id": "electrical/voltage-drop",
        "domain_frame": DomainFrame(
            discipline="electrical",
            subdomain="voltage-drop",
            role="senior electrical engineer",
            standards=["AS/NZS 3008.1"],
        ),
        "scenario": Scenario(summary="Calculate cable voltage drop."),
        "input_bundle": InputBundle(
            quantities=["load_current", "cable_length"],
            artifacts=[],
            assumptions=["impedance_method_required"],
        ),
        "reasoning_moves": ["calculation", "threshold_compliance"],
        "pressure_points": [
            PressurePoint(
                id="include_reactance_term",
                type="omitted_term",
                description="Use impedance method rather than resistance-only approximation.",
                confidence="high",
            )
        ],
        "output_contract": OutputContract(
            format="markdown_with_json_block",
            required_fields=["voltage_drop_v"],
            output_path="/workspace/output.md",
        ),
        "verifier_contract": VerifierContract(
            mode="deterministic_numeric",
            script="tests/test.sh",
            field_scores={"voltage_drop_v": "relative_tolerance"},
        ),
        "difficulty_controls": {"declared_difficulty": "easy"},
        "trajectory_affordances": {"expected_intermediate_steps": ["compute_voltage_drop"]},
        "extraction": ExtractionSummary(
            deterministic_fields=["domain_frame", "output_contract"],
            reasoning_review_fields=["pressure_points"],
            missing_fields=[],
        ),
    }
    payload.update(overrides)
    return TaskGenomeManifest.model_validate(payload)


def test_task_genome_manifest_accepts_valid_payload() -> None:
    manifest = build_manifest()

    assert manifest.task_id == "electrical/voltage-drop"
    assert manifest.domain_frame.discipline == "electrical"
    assert manifest.pressure_points[0].confidence == "high"


def test_source_span_rejects_absolute_path() -> None:
    with pytest.raises(ValidationError):
        SourceSpan(path="/tmp/tasks/electrical/voltage-drop", start_line=1, end_line=2)


def test_source_span_requires_a_complete_ordered_line_range() -> None:
    with pytest.raises(ValidationError, match="both start_line and end_line"):
        SourceSpan(path="instruction.md", start_line=1)
    with pytest.raises(ValidationError, match="must not precede"):
        SourceSpan(path="instruction.md", start_line=3, end_line=2)


def test_pressure_point_rejects_blank_description() -> None:
    with pytest.raises(ValidationError):
        PressurePoint(
            id="bad",
            type="omitted_term",
            description=" ",
            confidence="low",
        )


def test_task_genome_review_staleness_depends_only_on_task_snapshot() -> None:
    snapshot = _snapshot()
    review = TaskGenomeReview(
        task=snapshot,
        status="extracted",
        extractor="deterministic-task-genome",
        genome=build_manifest(),
        evidence={"instructions": [SourceSpan(path="instruction.md", start_line=1, end_line=2)]},
    )

    changed_review = review.model_copy(update={"reviewer": "theo", "status": "needs_review"})

    assert not changed_review.is_stale(snapshot)
    assert changed_review.is_stale(snapshot.model_copy(update={"task_id": "electrical/changed-voltage-drop"}))
    assert changed_review.task == review.task


def test_reviewed_task_genome_requires_a_reviewer() -> None:
    with pytest.raises(ValidationError, match="identify its reviewer"):
        TaskGenomeReview(
            task=_snapshot(),
            status="reviewed",
            extractor="deterministic-task-genome",
            genome=build_manifest(),
            evidence={"instructions": [SourceSpan(path="instruction.md", start_line=1, end_line=2)]},
        )


def _snapshot() -> TaskSnapshotRef:
    return TaskSnapshotRef(
        task_id="electrical/voltage-drop",
        artifact=ArtifactRef(
            artifact_id=f"artifacts/sha256/{'2' * 64}",
            sha256="2" * 64,
            size_bytes=1,
            media_type="application/vnd.aec-bench.task-snapshot+tar+zstd",
        ),
    )
