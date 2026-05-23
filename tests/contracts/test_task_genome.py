# ABOUTME: Tests for task genome sidecar contract models.
# ABOUTME: Verifies provenance, pressure points, and manifest validation behavior.

import pytest
from pydantic import ValidationError

from aec_bench.contracts.task_genome import (
    DomainFrame,
    ExtractionSummary,
    InputBundle,
    OutputContract,
    PressurePoint,
    ProvenanceRef,
    Scenario,
    TaskGenomeManifest,
    VerifierContract,
)


def build_manifest(**overrides: object) -> TaskGenomeManifest:
    payload = {
        "task_id": "electrical/voltage-drop",
        "source_task_path": "tasks/electrical/voltage-drop",
        "status": "extracted",
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
                provenance=[ProvenanceRef(file="instruction.md", section="Constraints", signal=None)],
                confidence="high",
                reviewed_by="deterministic_extractor",
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
    assert manifest.pressure_points[0].provenance[0].file == "instruction.md"


def test_task_genome_manifest_rejects_absolute_source_task_path() -> None:
    with pytest.raises(ValidationError):
        build_manifest(source_task_path="/tmp/tasks/electrical/voltage-drop")


def test_pressure_point_rejects_blank_description() -> None:
    with pytest.raises(ValidationError):
        PressurePoint(
            id="bad",
            type="omitted_term",
            description=" ",
            provenance=[],
            confidence="low",
            reviewed_by="deterministic_extractor",
        )
