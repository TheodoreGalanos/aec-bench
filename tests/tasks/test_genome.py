# ABOUTME: Tests for extracting task genome sidecar manifests from task directories.
# ABOUTME: Covers deterministic extraction from numeric and template-style task shapes.

from pathlib import Path

import yaml

from aec_bench.tasks.genome import (
    build_task_genome_evidence,
    extract_task_genome,
    task_genome_to_yaml,
)

TASKS_ROOT = Path(__file__).resolve().parents[2] / "tasks"


def test_extracts_voltage_drop_numeric_task_parts() -> None:
    manifest = extract_task_genome(TASKS_ROOT / "electrical" / "voltage-drop", TASKS_ROOT)

    assert manifest.task_id == "electrical/voltage-drop"
    assert manifest.domain_frame.discipline == "electrical"
    assert manifest.domain_frame.subdomain == "voltage-drop"
    assert "AS/NZS 3008.1" in manifest.domain_frame.standards
    assert "load_current" in manifest.input_bundle.quantities
    assert "impedance_method_required" in manifest.input_bundle.assumptions
    assert "calculation" in manifest.reasoning_moves
    assert "threshold_compliance" in manifest.reasoning_moves
    assert manifest.output_contract.format == "markdown_with_json_block"
    assert manifest.output_contract.required_fields == [
        "voltage_drop_v",
        "voltage_drop_pct",
        "compliance",
    ]
    assert manifest.verifier_contract.mode == "deterministic_numeric"
    assert manifest.verifier_contract.field_scores["compliance"] == "exact"
    assert any(point.type == "omitted_term" for point in manifest.pressure_points)
    assert "scenario" in manifest.extraction.reasoning_review_fields


def test_extracts_tool_backed_engineering_task_parts() -> None:
    manifest = extract_task_genome(
        TASKS_ROOT / "mechanical" / "heat-load" / "audit-office-building" / "sydney-8rm",
        TASKS_ROOT,
    )

    assert manifest.task_id == "mechanical/heat-load/audit-office-building/sydney-8rm"
    assert manifest.domain_frame.discipline == "mechanical"
    assert manifest.domain_frame.subdomain == "heat-load"
    assert "AS 1668.2" in manifest.domain_frame.standards
    assert "environment/heat_load_calc.py" in manifest.input_bundle.artifacts
    assert manifest.verifier_contract.mode == "scripted_verifier"
    assert manifest.output_contract.required_fields == [
        "errors_found",
        "room_no",
        "field",
        "given_value",
        "correct_value",
        "explanation",
    ]
    assert manifest.difficulty_controls["artifact_count"] == 3
    assert "source_task_mapping" not in manifest.extraction.reasoning_review_fields


def test_task_genome_yaml_round_trips_to_plain_sidecar_payload() -> None:
    manifest = extract_task_genome(TASKS_ROOT / "electrical" / "voltage-drop", TASKS_ROOT)

    payload = yaml.safe_load(task_genome_to_yaml(manifest))

    assert payload["task_id"] == "electrical/voltage-drop"
    assert payload["status"] == "extracted"
    assert payload["output_contract"]["format"] == "markdown_with_json_block"
    assert payload["extraction"]["reasoning_review_fields"]


def test_builds_model_facing_evidence_packet() -> None:
    packet = build_task_genome_evidence(
        TASKS_ROOT / "mechanical" / "heat-load" / "audit-office-building" / "sydney-8rm",
        TASKS_ROOT,
    )

    assert packet.task_id == "mechanical/heat-load/audit-office-building/sydney-8rm"
    assert "problem" in packet.instruction_sections
    assert "available_tool" in packet.instruction_sections
    assert "required" in packet.instruction_sections
    assert packet.deterministic_manifest.output_contract.required_fields == [
        "errors_found",
        "room_no",
        "field",
        "given_value",
        "correct_value",
        "explanation",
    ]
    assert "tests/test.sh" in packet.verifier_files
    assert "tests/verify.py" in packet.verifier_files
