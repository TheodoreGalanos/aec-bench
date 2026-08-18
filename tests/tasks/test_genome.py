# ABOUTME: Tests for extracting task genome sidecar manifests from task directories.
# ABOUTME: Covers deterministic extraction from numeric and template-style task shapes.

from pathlib import Path

import yaml

from aec_bench.contracts.run_bundle import TaskSnapshotRef
from aec_bench.contracts.task_genome import TaskGenomeReview
from aec_bench.harness.compilation.task_snapshot import build_task_snapshot
from aec_bench.ledger.artifact_repository import ArtifactRepository
from aec_bench.tasks.genome import (
    build_task_genome_review,
    extract_task_genome,
    load_task_genome_review,
    publish_task_genome_review,
    resolve_task_genome_evidence,
    task_genome_to_yaml,
)
from aec_bench.tasks.loader import load_task_definition

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
    assert "status" not in payload
    assert payload["output_contract"]["format"] == "markdown_with_json_block"
    assert payload["extraction"]["reasoning_review_fields"]


def test_builds_snapshot_bound_review_without_source_copies() -> None:
    task_dir = TASKS_ROOT / "mechanical" / "heat-load" / "audit-office-building" / "sydney-8rm"
    review, snapshot = _build_review(task_dir)

    assert review.task == snapshot
    assert review.task.task_id == "mechanical/heat-load/audit-office-building/sydney-8rm"
    assert review.extractor == "deterministic-task-genome"
    assert review.genome.output_contract.required_fields == [
        "errors_found",
        "room_no",
        "field",
        "given_value",
        "correct_value",
        "explanation",
    ]
    assert {span.path for span in review.evidence["verifier_contract"]} >= {
        "tests/test.sh",
        "tests/verify.py",
    }
    payload = review.model_dump(mode="json")
    assert "task_toml" not in payload
    assert "instruction_sections" not in payload
    assert "verifier_files" not in payload
    assert all(not hasattr(span, "sha256") for spans in review.evidence.values() for span in spans)


def test_review_evidence_resolves_only_against_its_task_snapshot() -> None:
    task_dir = TASKS_ROOT / "electrical" / "voltage-drop"
    review, snapshot = _build_review(task_dir)

    resolved = resolve_task_genome_evidence(review, task_dir=task_dir, current_task=snapshot)

    assert any("## Constraints" in excerpt for excerpt in resolved["instructions"])
    changed_snapshot = snapshot.model_copy(update={"package_sha256": "f" * 64})
    try:
        resolve_task_genome_evidence(review, task_dir=task_dir, current_task=changed_snapshot)
    except ValueError as error:
        assert str(error) == "task genome review is stale for the selected task snapshot"
    else:
        raise AssertionError("stale task genome evidence must not resolve")


def test_retained_review_uses_one_verified_artifact_reference(tmp_path: Path) -> None:
    task_dir = TASKS_ROOT / "electrical" / "voltage-drop"
    review, _ = _build_review(task_dir)
    repository = ArtifactRepository(tmp_path / "artifacts")

    ref = publish_task_genome_review(review, repository)

    assert load_task_genome_review(ref, repository) == review
    assert len(list((tmp_path / "artifacts").rglob(ref.sha256))) == 1


def _build_review(task_dir: Path) -> tuple[TaskGenomeReview, TaskSnapshotRef]:
    task = load_task_definition(task_dir, TASKS_ROOT)
    snapshot = build_task_snapshot(task=task, tasks_root=TASKS_ROOT)
    return build_task_genome_review(task_dir, TASKS_ROOT, task=snapshot), snapshot
